"""Discord ladder bot: queue, Elo, match reporting, slash-command preferences.

Matchmaking optimizes match settings for both players: preferences are scored numerically
(Preferred/Allowed/Never), compatible pairings are required, and selected settings
maximize the combined preference score for both sides.
"""

import glob
import json
import os
import random
from datetime import datetime
from typing import Optional

import discord
import numpy as np
from better_profanity import profanity
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# Constants and global state
# =============================================================================

def _parse_id_list(value: str) -> list[int]:
    return [int(x.strip()) for x in value.split(",") if x.strip()]


APPROVED_IDS = _parse_id_list(os.environ["DISCORD_APPROVED_IDS"])
OWNER_ID = int(os.environ.get("DISCORD_OWNER_ID", str(APPROVED_IDS[0])))
MY_GUILD = discord.Object(id=int(os.environ["DISCORD_GUILD_ID"]))
BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
profanity.load_censor_words()


# Queue to hold the players
player_queue = []
player_param_override = []
player_names_dodges={}
channel_ids_inq = os.environ["DISCORD_CHANNEL_IDS_INQ"].split(",")


dahvchennelid = os.environ["DISCORD_DAHV_CHANNEL_ID"]



class MyClient(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents=intents)
        # A CommandTree is a special type that holds all the application command
        # state required to make it work. This is a separate class because it
        # allows all the extra state to be opt-in.
        # Whenever you want to work with application commands, your tree is used
        # to store and work with them.
        # Note: When using commands.Bot instead of discord.Client, the bot will
        # maintain its own tree instead.
        self.tree = app_commands.CommandTree(self)

    # In this basic example, we just synchronize the app commands to one guild.
    # Instead of specifying a guild to every command, we copy over our global commands instead.
    # By doing so, we don't have to wait up to an hour until they are shown to the end-user.
    async def setup_hook(self):
        # This copies the global commands over to your guild.
        self.tree.copy_global_to(guild=MY_GUILD)


intents = discord.Intents.default()
client = MyClient(intents=intents)



# =============================================================================
# JSON persistence helpers
# =============================================================================

def check_and_create_file(filename, default_data):
    if not os.path.exists(filename):
        with open(filename, 'w') as f:
            json.dump(default_data, f)

def load_banned_players():
    check_and_create_file('banned_players.json', [])

    with open('banned_players.json', 'r') as f:
        return json.load(f)

def save_banned_players(banned_players):
    with open('banned_players.json', 'w') as f:
        json.dump(banned_players, f, indent=4)


# Load parameters from a JSON file
def load_parameters(user_id,override=False):
  inoverride=False
  if user_id in player_param_override:
    inoverride=True

  if override==False or inoverride==False:
    check_and_create_file('parameters.json', {})

    with open('parameters.json', 'r') as f:
        params = json.load(f)
    return params.get(str(user_id), {"CapPoint": "NONE", "Domination": "NONE", "Land Battle": "NONE", "Bo3": "Preferred", "Bo1": "Allowed", "Anonymous": "Allowed","standard_visibility":"Preferred","matrix3x3": "Allowed","pick3ban1": "Allowed","blind": "Never","pick1ban3": "Never","monthlyfun": "Never","no_global_bans": "Preferred","one_global_each": "Allowed","top_4_banned": "Allowed","UltraSize": "Preferred","LargeSize": "Never"})
  else: 
    check_and_create_file('parameters.json', {})

    with open('parameters.json', 'r') as f:
        params = json.load(f)

    paramsread=params.get(str(user_id), {"CapPoint": "NONE", "Domination": "NONE", "Land Battle": "NONE", "Bo3": "Preferred", "Bo1": "Allowed", "Anonymous": "Allowed","standard_visibility":"Preferred","matrix3x3": "Allowed","pick3ban1": "Allowed","blind": "Never","pick1ban3": "Never","monthlyfun": "Never","no_global_bans": "Preferred","one_global_each": "Allowed","top_4_banned": "Allowed","UltraSize": "Preferred","LargeSize": "Never"})
    paramsread["CapPoint"]='Preferred'
    paramsread["Domination"]='Never'
    paramsread["Land Battle"]='Never'
    paramsread["pick3ban1"]='Preferred'
    paramsread["monthlyfun"]='Never'
    paramsread["no_global_bans"]='Preferred'

    return paramsread
   

# Load parameters from a JSON file
def load_dodges(user_id):
    check_and_create_file('dodges.json', {})

    with open('dodges.json', 'r') as f:
        dodgesout = json.load(f)
    return dodgesout.get(str(user_id), {"Dodge1": "0", "Dodge2": "0", "Dodge3": "0"})


# Save parameters to a JSON file				
def save_parameters(user_id, params):
    check_and_create_file('parameters.json', {})
    with open('parameters.json', 'r') as f:
        data = json.load(f)
        data[str(user_id)] = params

    with open('parameters.json', 'w') as f:
        json.dump(data, f, indent=4)
# Save parameters to a JSON file

def save_dodges(user_id, dodgesin):
    check_and_create_file('dodges.json', {})
    with open('dodges.json', 'r') as f:
        data = json.load(f)
        data[str(user_id)] = dodgesin

    with open('dodges.json', 'w') as f:
        json.dump(data, f, indent=4)

# Load Elo ratings from a JSON file
def load_elo(user_id):
    check_and_create_file('elo.json', {})
    with open('elo.json', 'r') as f:
        elo = json.load(f)
    return elo.get(str(user_id), {"rating": 900, "wins": 0, "losses": 0, "total_games": 0})

# Load Elo ratings from a JSON file
def load_elo_dahv(user_id):
    check_and_create_file('elodahv.json', {})
    with open('elodahv.json', 'r') as f:
        elo = json.load(f)
    return elo.get(str(user_id), {"rating": 900, "wins": 0, "losses": 0, "total_games": 0})



# Save Elo ratings to a JSON file
def save_elo(user_id, elo):
    check_and_create_file('elo.json', {})
    with open('elo.json', 'r') as f:
        data = json.load(f)
        data[str(user_id)] = elo

    with open('elo.json', 'w') as f:
        json.dump(data, f, indent=4)

# Save Elo ratings to a JSON file
def save_elo_dahv(user_id, elo):
    check_and_create_file('elodahv.json', {})
    with open('elodahv.json', 'r') as f:
        data = json.load(f)
        data[str(user_id)] = elo

    with open('elodahv.json', 'w') as f:
        json.dump(data, f, indent=4)


# Load ongoing matches from a JSON file
def load_ongoing(user_id):
    check_and_create_file('ongoing.json', {})

    with open('ongoing.json', 'r') as f:
        ongoing = json.load(f)
    return ongoing.get(str(user_id), {"opponent": None, "match_type": None, "player_number": None})

# Save ongoing matches to a JSON file
def save_ongoing(user_id, ongoing):
    with open('ongoing.json', 'r') as f:
        data = json.load(f)
        data[str(user_id)] = ongoing

    with open('ongoing.json', 'w') as f:
        json.dump(data, f, indent=4)

# =============================================================================
# Queue, Elo, and match logic
# =============================================================================

def convertprefnum(inpref):
   if inpref.upper()=="PREFERRED":
     return 2
   if inpref.upper()=="ALLOWED":
     return 1
   if inpref.upper()=="NEVER":
     return 0


def find_random_max_index(arr):
    # Find the maximum value in the array
    max_val = np.max(arr)

    # Find the indices of the maximum value
    max_indices = np.where(arr == max_val)[0]

    # Return a random index from the indices of the maximum value
    return random.choice(max_indices)
  




# Check for a match in the queue
def check_match(queue, user_id):
    userparams = load_parameters(user_id,override=True)
    userdodges = load_dodges(user_id)
    try:   
      userdodgelist=[int(userdodges['Dodge1']),int(userdodges['Dodge2']),int(userdodges['Dodge3'])]
    except: 
      userdodgelist=[0,0,0]
    modesstr=['CapPoint','Domination','Land Battle']
    serieslengthstr=['Bo3','Bo1']
    pickformatstr=['matrix3x3','pick3ban1','blind','pick1ban3','monthlyfun']
    anonliststr=['Anonymous', 'standard_visibility']
    globalbanstr=['no_global_bans', 'one_global_each','top_4_banned']
    unitsizestr=['UltraSize', 'LargeSize']


    found=False
    modelistuser=np.array([convertprefnum(userparams['CapPoint']),convertprefnum(userparams['Domination']),convertprefnum(userparams['Land Battle'])])
    serieslengthuser=np.array([convertprefnum(userparams['Bo3']),convertprefnum(userparams['Bo1']),convertprefnum('Never')])
    pickformatuser=np.array([convertprefnum(userparams['matrix3x3']),convertprefnum(userparams['pick3ban1']),convertprefnum(userparams['blind']),convertprefnum(userparams['pick1ban3']),convertprefnum(userparams['monthlyfun'])])

    anonlistuser=np.array([convertprefnum(userparams['Anonymous']),convertprefnum(userparams['standard_visibility']),convertprefnum('Never')])
    globalbanlistuser=np.array([convertprefnum(userparams['no_global_bans']),convertprefnum(userparams['one_global_each']),convertprefnum(userparams['top_4_banned'])])
    unitsizelistuser=np.array([convertprefnum(userparams['UltraSize']),convertprefnum(userparams['LargeSize']),convertprefnum('Never')])
    selectedmatch=['','','','']
    for player in queue:
        playerparams = load_parameters(player,override=True)
        playerdodges= load_dodges(player)
        try:
           playerdodgelist=[str(playerdodges['Dodge1']),str(playerdodges['Dodge2']),str(playerdodges['Dodge3'])]
        except:
           playerdodgelist=[str(playerdodges['Dodge1']),str(playerdodges['Dodge2']),str(playerdodges['Dodge3'])]
      # Check if user_id is in playerdodgelist and if player_id is in userdodgelist
        if str(user_id) in playerdodgelist or int(player) in userdodgelist or player_names_dodges[str(user_id)] in playerdodgelist or player_names_dodges[str(player)] in userdodgelist :
                continue  # Skip this player and go to the next one in the queue
        
        if player != user_id:
            modelist=np.array([convertprefnum(playerparams['CapPoint']),convertprefnum(playerparams['Domination']),convertprefnum(playerparams['Land Battle'])])
            serieslength=np.array([convertprefnum(playerparams['Bo3']),convertprefnum(playerparams['Bo1']),convertprefnum('Never')])
            pickformat=np.array([convertprefnum(playerparams['matrix3x3']),convertprefnum(playerparams['pick3ban1']),convertprefnum(playerparams['blind']),convertprefnum(playerparams['pick1ban3']),convertprefnum(playerparams['monthlyfun'])])
            anonlist=np.array([convertprefnum(playerparams['Anonymous']),convertprefnum(playerparams['standard_visibility']),convertprefnum('Never')])
            globalbanlist=np.array([convertprefnum(playerparams['no_global_bans']),convertprefnum(playerparams['one_global_each']),convertprefnum(playerparams['top_4_banned'])])
            unitsizelist=np.array([convertprefnum(playerparams['UltraSize']),convertprefnum(playerparams['LargeSize']),convertprefnum('Never')])

            if  np.dot(np.sign(modelist),np.sign(modelistuser))>0 and  np.dot(np.sign(pickformat),np.sign(pickformatuser))>0 and  np.dot(np.sign(serieslength),np.sign(serieslengthuser))>0 and np.dot(np.sign(anonlist),np.sign(anonlistuser))>0 and np.dot(np.sign(globalbanlist),np.sign(globalbanlistuser))>0 and np.dot(np.sign(unitsizelist),np.sign(unitsizelistuser))>0:


                totalmode=find_random_max_index(np.sign(modelist)*np.sign(modelistuser)*(modelist+modelistuser))
                totalserieslength=find_random_max_index(np.sign(serieslength)*np.sign(serieslengthuser)*(serieslength+serieslengthuser))
                totalpickformat=find_random_max_index(np.sign(pickformat)*np.sign(pickformatuser)*(pickformat+pickformatuser))
                totalanon=find_random_max_index(np.sign(anonlist)*np.sign(anonlistuser)*(anonlist+anonlistuser))
                totalglobalban=find_random_max_index(np.sign(globalbanlist)*np.sign(globalbanlistuser)*(globalbanlist+globalbanlistuser))
                totalunitsize=find_random_max_index(np.sign(unitsizelist)*np.sign(unitsizelistuser)*(unitsizelist+unitsizelistuser))



                selectedmatch=[modesstr[totalmode], serieslengthstr[totalserieslength],pickformatstr[totalpickformat], anonliststr[totalanon],globalbanstr[totalglobalban],unitsizestr[totalunitsize]]
                found=True
                return found, player,selectedmatch
    return found, None, selectedmatch

# Calculate the new Elo rating after a match
def calculate_elo(rating1, rating2, result,lengthfactor):
    K = 32*lengthfactor
    expected1 = 1 / (1 + 10 ** ((rating2 - rating1) / 400))
    expected2 = 1 / (1 + 10 ** ((rating1 - rating2) / 400))
    new_rating1 = rating1 + K * (result - expected1)
    new_rating2 = rating2 + K * ((1 - result) - expected2)
    return new_rating1, new_rating2






def getmodemessage(instr):
   modesstr=['CapPoint','Domination','Land Battle']
   pathstr=[r'MatchFoundText\Modes\LBwCap.txt',r'MatchFoundText\Modes\Domination.txt',r'MatchFoundText\Modes\LBwRules.txt']
   for i in range(len(modesstr)):
      if instr==modesstr[i]:
         with open(pathstr[i], 'r') as f:
             content = f.read()
         return content+'\n'
   return 'No text found for '+instr

def getanonmessage(instr):
   modesstr=['Anonymous','standard_visibility']
   pathstr=[r'MatchFoundText\Anonymous\anonymous.txt',r'MatchFoundText\Anonymous\standard.txt']
   for i in range(len(modesstr)):
      if instr==modesstr[i]:
         with open(pathstr[i], 'r') as f:
             content = f.read()
         return content+'\n'
   return 'No text found for '+instr

def getunitsizemessage(instr):
   modesstr=['UltraSize','LargeSize']
   pathstr=[r'MatchFoundText\UnitSize\ULTRASIZE.txt',r'MatchFoundText\UnitSize\LARGESIZE.txt']
   for i in range(len(modesstr)):
      if instr==modesstr[i]:
         with open(pathstr[i], 'r') as f:
             content = f.read()
         return content+'\n'
   return 'No text found for '+instr


def getglobalbanmessage(instr):
   modesstr=['no_global_bans','one_global_each','top_4_banned']
   pathstr=[r'MatchFoundText\GlobalBan\noglobalbans.txt',r'MatchFoundText\GlobalBan\oneglobaleach.txt',r'MatchFoundText\GlobalBan\top4banned.txt']
   for i in range(len(modesstr)):
      if instr==modesstr[i]:
         with open(pathstr[i], 'r') as f:
             content = f.read()
         return content+'\n'
   return 'No text found for '+instr



def getcommandsmessage():

   pathstr=r'MatchFoundText\commands\commands.txt'
   with open(pathstr, 'r') as f:
             contentnow = f.read()
   return contentnow



def getrulesmessage(instr):
   modesstr=['CapPoint','Domination','Land Battle']
   pathstr=[r'MatchFoundText\Rules\LBwCapRules.txt',r'MatchFoundText\Rules\DominationRules.txt',r'MatchFoundText\Rules\LBwRulesRules.txt']
   for i in range(len(modesstr)):
      if instr==modesstr[i]:
         with open(pathstr[i], 'r') as f:
             content = f.read()
         return content+'\n'
   content=''
   if instr=='':
      for i in range(len(modesstr)):

         with open(pathstr[i], 'r') as f:
             contentnow = f.read()
             content+=contentnow
         content+='\n' 
   return content


def getserieslengthandpickmessage(instr1,instr2):
   modesstr=['matrix3x3','pick3ban1','blind','pick1ban3','monthlyfun']
   lenstr=['Bo3','Bo1']

   pathstr=[r'MatchFoundText\PickandSeriesLength\MATRIX3X3',r'MatchFoundText\PickandSeriesLength\PICK3BAN1',r'MatchFoundText\PickandSeriesLength\BLIND',r'MatchFoundText\PickandSeriesLength\PICK1BAN3',r'MatchFoundText\PickandSeriesLength\MONTHLYFUN']
   pathlenstr=['BO3.txt','BO1.txt']
   
   for i in range(len(modesstr)):
    for j in range(len(lenstr)):
      if instr1==modesstr[i] and instr2==lenstr[j]:
         with open(pathstr[i]+pathlenstr[j], 'r') as f:
             content = f.read()
         return content+'\n'
   return 'No text found for '+instr1+instr2



def getmaps(instr,instr2):
   modesstr=['CapPoint','Domination','Land Battle']
   pathstr=[r'Maps\capmaps.txt',r'Maps\dommaps.txt',r'Maps\landmaps.txt']

   if instr2=='Bo3':
      n=3
   else:
      n=1

   for i in range(len(modesstr)):
      if instr==modesstr[i]:
         with open(pathstr[i], 'r') as f:
             maps = f.readlines()
   
   selectedmaps=random.sample(maps,n)
   outstr='The maps are:\n'

   for i in range(len(selectedmaps)):
      outstr+=selectedmaps[i]
   return outstr



# Slash command to join the queue
# =============================================================================
# Slash commands
# =============================================================================

@client.tree.command(name="join")
async def join(interaction: discord.Interaction):
    user_id = interaction.user.id
    user_ongoing = load_ongoing(user_id)
    command_channel=interaction.channel_id
    usernameupdate= await  client.fetch_user(user_id)
    player_names_dodges[str(user_id)]=   usernameupdate.name



    # Check if the user has an ongoing match
    banned_players = load_banned_players()

    # Check if the user is banned
    if str(user_id) in banned_players:
        await interaction.response.send_message(f"{interaction.user.mention}, you are banned from joining the queue.")
        return

    paramcheck=load_parameters(user_id)
    if paramcheck['CapPoint']=="NONE" and command_channel!=dahvchennelid:
        await interaction.response.send_message(f"Please update your mode parameters before joining the que! Use /update_modes.")
        return   



    if user_ongoing["opponent"] is not None:
        await interaction.response.send_message(f"{interaction.user.mention}, you cannot join the queue because you have an ongoing match.")
        print('ongoingmatch')
    elif user_id not in player_queue:
        if dahvchennelid==str(command_channel): 
           await interaction.channel.send("Joining queue using Dahv Company server settings (Cap point mod only, and Pick 3 ban 1 perferred)!")
        player_queue.append(user_id)
        if dahvchennelid==str(command_channel): 
            player_param_override.append(user_id)

        print('userjoin')
        print('joined')
        # Check for a match
        foundmatch,match,selectedgame = check_match(player_queue, user_id)
        if foundmatch:
            # Randomly assign Player 1 and Player 2
            players = [user_id, match]
            random.shuffle(players)
            matchtype= ''.join(selectedgame)
            # Update ongoing matches
            user_ongoing["opponent"] = match
            user_ongoing["match_type"] =  ''.join(selectedgame)   # Replace with actual match type
            user_ongoing["player_number"] = players.index(user_id) + 1
            save_ongoing(user_id, user_ongoing)

            match_ongoing = load_ongoing(match)
            match_ongoing["opponent"] = user_id
            match_ongoing["match_type"] =  ''.join(selectedgame)  # Replace with actual match type
            match_ongoing["player_number"] = players.index(match) + 1
            save_ongoing(match, match_ongoing)
            # Remove players from the queue
            player_queue.remove(user_id)
            player_queue.remove(match)
            try: 
              player_param_override.remove(user_id)
              player_param_override.remove(match)
            except: 
               errorfoundvalue=1
            # Send DM to both players
            await interaction.channel.send(f"{interaction.user.mention} has joined the queue.")

            user =await  client.fetch_user(user_id)
            opponent = await client.fetch_user(match)
            matchmessage=''
            modemessage=getmodemessage( selectedgame[0])
            anonmessage=getanonmessage( selectedgame[3])
            unitsizemessage=getunitsizemessage( selectedgame[5])
            globalbanmessage=getglobalbanmessage(  selectedgame[4]  )
            gamelenstr=f'This is a {selectedgame[1]} match.\n PICK FORMAT:\n' 
            pickformatstr=getserieslengthandpickmessage(selectedgame[2],selectedgame[1])
            mapsmessage=getmaps(selectedgame[0],selectedgame[1])
            matchmessage=anonmessage+modemessage+unitsizemessage+gamelenstr+globalbanmessage+pickformatstr+mapsmessage

            if 'ANONYMOUS' in matchtype.upper():
              await user.send(f"You have a match! You are Player {user_ongoing['player_number']}, your opponent is Player {match_ongoing['player_number']}.\n"+matchmessage)
              await opponent.send(f"You have a match! You are Player {match_ongoing['player_number']}, your opponent is Player {user_ongoing['player_number']}.\n"+matchmessage)





            else:
              await user.send(f"You have a match against <@{match}> (AKA { opponent.name})! You are Player {user_ongoing['player_number']}, your opponent is Player {match_ongoing['player_number']}.\n"+matchmessage)
              await opponent.send(f"You have a match against {user.mention} (AKA { user.name})! You are Player {match_ongoing['player_number']}, your opponent is Player {user_ongoing['player_number']}.\n"+matchmessage)

              await interaction.response.send_message(f"Match found for {interaction.user.mention}!")

        else: 
            await interaction.response.send_message(f"{interaction.user.mention} has joined the queue.")
            for channelalertid in channel_ids_inq:
               channelalert = await client.fetch_channel(channelalertid)
               await channelalert.send('A player is now waiting in queue!')
            paramscheckcap=load_parameters(user_id)
            if paramscheckcap['CapPoint'].upper()!='NEVER':
                channelalert = await client.fetch_channel(dahvchennelid)
                await channelalert.send('A player is now waiting in queue for Dahv ladder!')


    else:
            await interaction.response.send_message(f"{interaction.user.mention}, you are already in the queue.")


@client.tree.command(name="update_modes")
@app_commands.choices(landbattle_cappoint=[
    app_commands.Choice(name='Preferred', value='preferred'),
    app_commands.Choice(name='Allowed', value='allowed'),
    app_commands.Choice(name='Never', value='never')
])
@app_commands.choices(domination=[
    app_commands.Choice(name='Preferred', value='preferred'),
    app_commands.Choice(name='Allowed', value='allowed'),
    app_commands.Choice(name='Never', value='never')
])
@app_commands.choices(landbattle_rules=[
    app_commands.Choice(name='Preferred', value='preferred'),
    app_commands.Choice(name='Allowed', value='allowed'),
    app_commands.Choice(name='Never', value='never')
])
async def update_modes(interaction: discord.Interaction, landbattle_cappoint: app_commands.Choice[str], domination:app_commands.Choice[str], landbattle_rules:app_commands.Choice[str]):
    user_id = interaction.user.id

    # Load the existing parameters
    params = load_parameters(user_id)
    # Update the parameters if new values are provided
    if landbattle_cappoint.value is not None:
        params["CapPoint"] = landbattle_cappoint.value
    if domination.value is not None:
        params["Domination"] = domination.value
    if landbattle_rules.value is not None:
        params["Land Battle"] = landbattle_rules.value
    # Save the updated parameters
    save_parameters(user_id, params)
    await interaction.response.send_message(f"Your current parameters are:\n"                 
                      f"GAME MODE\n"
                      f"Land Battle cappoint: {params['CapPoint']}\n"
                      f"Domination: {params['Domination']}\n"
                      f"Landbattle with rules: {params['Land Battle']}\n")


@client.tree.command(name="update_global_bans")
@app_commands.choices(no_global_bans=[
    app_commands.Choice(name='Preferred', value='preferred'),
    app_commands.Choice(name='Allowed', value='allowed'),
])
@app_commands.choices(one_global_each=[
    app_commands.Choice(name='Preferred', value='preferred'),
    app_commands.Choice(name='Allowed', value='allowed'),
    app_commands.Choice(name='Never', value='never')
])
@app_commands.choices(top_4_banned=[
    app_commands.Choice(name='Preferred', value='preferred'),
    app_commands.Choice(name='Allowed', value='allowed'),
    app_commands.Choice(name='Never', value='never')
])
async def update_global_bans(interaction: discord.Interaction, no_global_bans: app_commands.Choice[str], one_global_each:app_commands.Choice[str], top_4_banned:app_commands.Choice[str]):
    user_id = interaction.user.id
    # Load the existing parameters
    params = load_parameters(user_id)
    # Update the parameters if new values are provided
    if no_global_bans.value is not None:
        params["no_global_bans"] = no_global_bans.value
    if one_global_each.value is not None:
        params["one_global_each"] = one_global_each.value
    if top_4_banned.value is not None:
        params["top_4_banned"] = top_4_banned.value
    # Save the updated parameters
    save_parameters(user_id, params)
    await interaction.response.send_message(f"Your current parameters are:\n"
                      f"GLOBAL BANS\n"
                      f"no_global_bans: {params['no_global_bans']}\n"
                      f"one_global_each: {params['one_global_each']}\n"
                      f"top_4_banned: {params['top_4_banned']}\n")


@client.tree.command(name="update_length")
@app_commands.choices(bo3=[
    app_commands.Choice(name='Preferred', value='preferred'),
    app_commands.Choice(name='Allowed', value='allowed'),
    app_commands.Choice(name='Never', value='never')

])
@app_commands.choices(bo1=[
    app_commands.Choice(name='Preferred', value='preferred'),
    app_commands.Choice(name='Allowed', value='allowed'),
])
async def update_length(interaction: discord.Interaction, bo3: app_commands.Choice[str], bo1:app_commands.Choice[str]):
    user_id = interaction.user.id
    # Load the existing parameters
    params = load_parameters(user_id)
    # Update the parameters if new values are provided

    if bo3.value is not None:
        params["Bo3"] = bo3.value
    if bo1.value is not None:
        params["Bo1"] = bo1.value

    # Save the updated parameters
    save_parameters(user_id, params)
    await interaction.response.send_message(f"Your current parameters are:\n"
                      f"SERIES LENGTH\n"
                      f"Bo3: {params['Bo3']}\n"
                      f"Bo1: {params['Bo1']}\n")

@client.tree.command(name="update_unit_size")
@app_commands.choices(ultra=[
    app_commands.Choice(name='Preferred', value='preferred'),
    app_commands.Choice(name='Allowed', value='allowed'),
])
@app_commands.choices(large=[
    app_commands.Choice(name='Preferred', value='preferred'),
    app_commands.Choice(name='Allowed', value='allowed'),
    app_commands.Choice(name='Never', value='never')
])
async def update_length(interaction: discord.Interaction, ultra: app_commands.Choice[str], large:app_commands.Choice[str]):
    user_id = interaction.user.id
    # Load the existing parameters
    params = load_parameters(user_id)
    # Update the parameters if new values are provided

    if ultra.value is not None:
        params["UltraSize"] = ultra.value
    if large.value is not None:
        params["LargeSize"] = large.value

    # Save the updated parameters
    save_parameters(user_id, params)
    await interaction.response.send_message(f"Your current parameters are:\n"
                      f"UNIT SIZE\n"
                      f"UltraSize: {params['UltraSize']}\n"
                      f"LargeSize: {params['LargeSize']}\n")



@client.tree.command(name="update_pick_system")
@app_commands.choices(matrix3x3=[
    app_commands.Choice(name='Preferred', value='preferred'),
    app_commands.Choice(name='Allowed', value='allowed'),
    app_commands.Choice(name='Never', value='never')
])
@app_commands.choices(pick3ban1=[
    app_commands.Choice(name='Preferred', value='preferred'),
    app_commands.Choice(name='Allowed', value='allowed'),
    app_commands.Choice(name='Never', value='never')
])
@app_commands.choices(blind=[
    app_commands.Choice(name='Preferred', value='preferred'),
    app_commands.Choice(name='Allowed', value='allowed'),
    app_commands.Choice(name='Never', value='never')
])
@app_commands.choices(pick1ban3=[
    app_commands.Choice(name='Preferred', value='preferred'),
    app_commands.Choice(name='Allowed', value='allowed'),
    app_commands.Choice(name='Never', value='never')
])
@app_commands.choices(monthlyfun=[
    app_commands.Choice(name='Preferred', value='preferred'),
    app_commands.Choice(name='Allowed', value='allowed'),
    app_commands.Choice(name='Never', value='never')
])
async def update_pick_system(interaction: discord.Interaction, matrix3x3: app_commands.Choice[str], pick3ban1:app_commands.Choice[str],blind: app_commands.Choice[str], pick1ban3:app_commands.Choice[str], monthlyfun:app_commands.Choice[str]):
    user_id = interaction.user.id
    # Load the existing parameters
    params = load_parameters(user_id)
    # Update the parameters if new values are provided

    if matrix3x3.value is not None:
        params["matrix3x3"] = matrix3x3.value
    if pick3ban1.value is not None:
        params["pick3ban1"] = pick3ban1.value
    if blind.value is not None:
        params["blind"] = blind.value
    if pick1ban3.value is not None:
        params["pick1ban3"] = pick1ban3.value
    if monthlyfun.value is not None:
        params["monthlyfun"] = monthlyfun.value
    # Save the updated parameters
    save_parameters(user_id, params)
    
    await interaction.response.send_message(f"Your current parameters are:\n"
                      f"PICK SYSTEM\n"
                      f"matrix3x3: {params['matrix3x3']}\n"
                      f"pick3ban1: {params['pick3ban1']}\n"
                      f"blind: {params['blind']}\n"
                      f"pick1ban3: {params['pick1ban3']}\n"
                      f"monthlyfun: {params['monthlyfun']}")

    if pick3ban1.value=='never':
      await interaction.channel.send(f"It is highly recommended to set pick3ban1 to allowed to increase your chances of getting a match!")




@client.tree.command(name="update_anonymous")
@app_commands.choices(anonymous=[
    app_commands.Choice(name='Preferred', value='preferred'),
    app_commands.Choice(name='Allowed', value='allowed'),
    app_commands.Choice(name='Never', value='never')
])
@app_commands.choices(standard_visibility=[
    app_commands.Choice(name='Preferred', value='preferred'),
    app_commands.Choice(name='Allowed', value='allowed'),
    app_commands.Choice(name='Never', value='never')
])
async def update_anonymous(interaction: discord.Interaction, anonymous: app_commands.Choice[str],standard_visibility: app_commands.Choice[str]):
    user_id = interaction.user.id
    # Load the existing parameters
    params = load_parameters(user_id)
    # Update the parameters if new values are provided

    if anonymous.value is not None:
        params["Anonymous"] = anonymous.value
    if standard_visibility.value is not None:
        params["standard_visibility"] = standard_visibility.value    # Save the updated parameters
    save_parameters(user_id, params)
    await interaction.response.send_message(f"Your current parameters are:\n"
                      f"ANONYMITY\n"
                      f"Anonymous: {params['Anonymous']}\n"
                      f"standard_visibility: {params['standard_visibility']}\n")


@client.tree.command(name="update_dodges")
async def update_dodges(interaction: discord.Interaction, dodge1: str = None, dodge2: str = None, dodge3: str = None):
    user_id = interaction.user.id
    # Load the existing parameters
    params = load_dodges(user_id)
    # Update the parameters if new values are provided
    if dodge1 is not None:
        params["Dodge1"] = dodge1
    if dodge2 is not None:
        params["Dodge2"] = dodge2
    if dodge3 is not None:
        params["Dodge3"] = dodge3
       # Save the updated parameters
    save_dodges(user_id, params)
    await interaction.response.send_message(f"Your current parameters are:\n"
                      f"Dodge1: {params['Dodge1']}\n"
                      f"Dodge2: {params['Dodge2']}\n"
                      f"Dodge3: {params['Dodge3']}\n")

@client.tree.command(name="report_result")
@app_commands.choices(outcome=[
    app_commands.Choice(name='Win', value='win'),
    app_commands.Choice(name='Lose', value='loss'),
    app_commands.Choice(name='Exit', value='exit')
])
async def report_result(interaction: discord.Interaction, outcome: app_commands.Choice[str	]):
    user_id = interaction.user.id
    user_elo = load_elo(user_id)
    user_ongoing = load_ongoing(user_id)
    result=outcome.value
    # Check if the user has an ongoing match
    if user_ongoing["opponent"] is not None:
        opponent_id = user_ongoing["opponent"]
        opponent_elo = load_elo(opponent_id)
        opponent_ongoing = load_ongoing(opponent_id)
        oldeloopp=opponent_elo["rating"]
        oldelouser=user_elo["rating"]

        serieslengthfactor=1
        if  'BO1' in user_ongoing["match_type"].upper() :
              serieslengthfactor=.5   
 
        # Update Elo ratings based on the result
        if result == "win":
            user_elo["wins"] += 1
            opponent_elo["losses"] += 1
            user_elo["rating"], opponent_elo["rating"] = calculate_elo(user_elo["rating"], opponent_elo["rating"], 1,serieslengthfactor)
        elif result == "loss":
            user_elo["losses"] += 1
            opponent_elo["wins"] += 1
            user_elo["rating"], opponent_elo["rating"] = calculate_elo(user_elo["rating"], opponent_elo["rating"], 0,serieslengthfactor)

        if result != "exit":
            user_elo["total_games"] += 1
            opponent_elo["total_games"] += 1
        
        
        
        neweloopp=opponent_elo["rating"]
        newelouser=user_elo["rating"]

        save_elo(user_id, user_elo)
        save_elo(opponent_id, opponent_elo)

        # Save match details to a file
        match_details = {
            "match_type": user_ongoing["match_type"],
            "player_ids": [user_id, opponent_id],
            "winner": user_id if result == "win" else opponent_id if result == "loss" else "exit",
            "elochange": [newelouser-oldelouser,neweloopp-oldeloopp],
            "date_time_reported": datetime.now().isoformat()
        }
        with open('match_record.json', 'a') as f:
            f.write(json.dumps(match_details) + '\n')
        dahvmessage=False
        if 'CAPPOINT' in user_ongoing["match_type"].upper(): #and 'BO3' in user_ongoing["match_type"].upper() and 'PICK3BAN1' in user_ongoing["match_type"].upper() and 'NO_GLOBAL_BANS' in user_ongoing["match_type"].upper():
            dahvmessage=True
            user_elodahv = load_elo_dahv(user_id)
            opponent_elodahv = load_elo_dahv(opponent_id)
            oldelooppdahv=opponent_elodahv["rating"]
            oldelouserdahv=user_elodahv["rating"]


        # Update Elo ratings based on the result
            if result == "win":
                user_elodahv["wins"] += 1
                opponent_elodahv["losses"] += 1
                user_elodahv["rating"], opponent_elodahv["rating"] = calculate_elo(user_elodahv["rating"], opponent_elodahv["rating"], 1,serieslengthfactor)
            elif result == "loss":
                 user_elodahv["losses"] += 1
                 opponent_elodahv["wins"] += 1
                 user_elodahv["rating"], opponent_elodahv["rating"] = calculate_elo(user_elodahv["rating"], opponent_elodahv["rating"], 0,serieslengthfactor)

            if result != "exit":
                 user_elodahv["total_games"] += 1
                 opponent_elodahv["total_games"] += 1
             
        
       
            newelooppdahv=opponent_elodahv["rating"]
            newelouserdahv=user_elodahv["rating"]

            save_elo_dahv(user_id, user_elodahv)
            save_elo_dahv(opponent_id, opponent_elodahv)
                  
        # Remove the ongoing match for both players
        user_ongoing["opponent"] = None
        user_ongoing["match_type"] = None
        user_ongoing["player_number"] = None
        save_ongoing(user_id, user_ongoing)

        opponent_ongoing["opponent"] = None
        opponent_ongoing["match_type"] = None
        opponent_ongoing["player_number"] = None
        save_ongoing(opponent_id, opponent_ongoing)


        user =await  client.fetch_user(user_id)
        opponent = await client.fetch_user(opponent_id )

        await user.send(f"Your match result has been recorded. Good game! Your elo has gone from {int(oldelouser)}->{int(newelouser)}. You reported {result}")
        await opponent.send(f"Your match result has been recorded. Good game! Your elo has gone from {int(oldeloopp)}->{int(neweloopp)}. Your opponent reported {result}.")
        if dahvmessage==True:

           await user.send(f"Your match counts towards Dahv Ladder. Your elo has gone from {int(oldelouserdahv)}->{int(newelouserdahv)}. You reported {result}")
           await opponent.send(f"Your match counts towards Dahv Ladder. Your elo has gone from {int(oldelooppdahv)}->{int(newelooppdahv)}. Your opponent reported {result}.")     
       
        await  interaction.response.send_message(f"Match reported, please check your DMs.")

 
    else:
        await  interaction.response.send_message(f"You don't have any ongoing matches.")

@client.tree.command(name="send_message")
async def send_message(interaction: discord.Interaction, sendmessage: str):
    user_id = interaction.user.id
    user_ongoing = load_ongoing(user_id)

    if profanity.contains_profanity(sendmessage):
          await  interaction.response.send_message(f"Your message was determined to contain profanity. Please rephrase.")
          return
    # Check if the user has an ongoing match
    if user_ongoing["opponent"] is not None:
        opponent_id = user_ongoing["opponent"]
        matchtype= user_ongoing["match_type"]
        opponent = await client.fetch_user(opponent_id)
        print(matchtype)
        if 'ANONYMOUS' in matchtype.upper():
          await opponent.send(f"Your opponent says: {sendmessage}")
          await  interaction.response.send_message(f"Your message has been sent to your opponent. This message was:\n {sendmessage}")


        else:
          await opponent.send(f"Your opponent {interaction.user.mention} (AKA {interaction.user.name}) says: {sendmessage}")
          await  interaction.response.send_message(f"Your message has been sent to your opponent. This message was:\n {sendmessage}")
    else:
        await  interaction.response.send_message(f"You don't have any ongoing matches.")

@client.tree.command(name="leave")
async def leave(interaction: discord.Interaction):
    user_id = interaction.user.id

    # Check if the user is in the queue
    if user_id in player_queue:
        player_queue.remove(user_id)
        try: 
            player_param_override.remove(user_id)
        except: 
               errorfoundvalue=1
        await  interaction.response.send_message(f"{interaction.user.mention} has left the queue.")
    else:
        await  interaction.response.send_message(f"{interaction.user.mention}, you are not in the queue.")


@client.tree.command(name="view_params")
async def view_params(interaction: discord.Interaction):
    user_id = interaction.user.id
    params = load_parameters(user_id)
    await interaction.response.send_message(f"Your current parameters are:\n"
                      f"GAME MODE\n"
                      f"Land battle with CapPoint: {params['CapPoint']}\n"
                      f"Domination: {params['Domination']}\n"
                      f"Land Battle with Rules: {params['Land Battle']}\n"
                      f"SERIES LENGTH\n"
                      f"Bo3: {params['Bo3']}\n"
                      f"Bo1: {params['Bo1']}\n"
                      f"ANONYMITY\n"
                      f"Anonymous: {params['Anonymous']}\n"
                      f"standard_visibility: {params['standard_visibility']}\n"
                      f"PICK SYSTEM\n"
                      f"matrix3x3: {params['matrix3x3']}\n"
                      f"pick3ban1: {params['pick3ban1']}\n"
                      f"blind: {params['blind']}\n"
                      f"pick1ban3: {params['pick1ban3']}\n"
                      f"monthlyfun: {params['monthlyfun']}\n"
                      f"GLOBAL BANS\n"
                      f"no_global_bans: {params['no_global_bans']}\n"
                      f"one_global_each: {params['one_global_each']}\n"
                      f"top_4_banned: {params['top_4_banned']}\n"
                      f"UNIT SIZE\n"
                      f"UltraSize: {params['UltraSize']}\n"
                      f"LargeSize: {params['LargeSize']}\n")

@client.tree.command(name="ladderban")
async def ladderban(interaction: discord.Interaction, bannedid: str):
    if interaction.user.id not in APPROVED_IDS:
        await interaction.response.send_message("Sorry, you are not authorized to use this command.")
        return    # Load the ongoing match for the input UserID    # Load banned players
    banned_players = load_banned_players()

    # Add user to banned players
    banned_players.append(str(bannedid))

    # Save banned players
    save_banned_players(banned_players)

    await interaction.channel.send(f"<@{bannedid}> has been banned from joining the queue.")





@client.tree.command(name="ladderunban")
async def ladderunban(interaction: discord.Interaction, bannedid: str):
    if interaction.user.id not in APPROVED_IDS:
        await interaction.response.send_message("Sorry, you are not authorized to use this command.")
        return    # Load the ongoing match for the input UserID

    banned_players = load_banned_players()

    # Remove user from banned players
    if bannedid in banned_players:
        banned_players.remove(bannedid)

    # Save banned players
    save_banned_players(banned_players)

    await interaction.channel.send(f"<@{bannedid}> has been unbanned from joining the queue.")


@client.tree.command(name='sync', description='Owner only')
async def sync(interaction: discord.Interaction):
    if interaction.user.id == OWNER_ID:
        print('Command tree synced.')
        await client.tree.sync()

    else:
        await interaction.response.send_message('You must be the owner to use this command!')



@client.tree.command(name='commands')
async def commands(interaction: discord.Interaction):
    user_id = interaction.user.id
    user_ongoing = load_ongoing(user_id)
    messagesendnow=getcommandsmessage()



    await interaction.response.send_message(messagesendnow)
    return

@client.tree.command(name='help')
async def help(interaction: discord.Interaction):
    user_id = interaction.user.id
    user_ongoing = load_ongoing(user_id)
    messagesendnow=getcommandsmessage()

    await interaction.response.send_message(messagesendnow)
    return


@client.tree.command(name='rules')
async def rules(interaction: discord.Interaction):
    user_id = interaction.user.id
    user_ongoing = load_ongoing(user_id)
    modeslistcheck= ['CapPoint','Domination','Land Battle']    
    # Check if the user has an ongoing match
    messagesendnow=''
    if user_ongoing["opponent"] is not None:
       for j in range(len(modeslistcheck)):
              if   modeslistcheck[j] in  user_ongoing["match_type"]:
                   messagesendnow=getrulesmessage(modeslistcheck[j])
                   
    else: 
        messagesendnow=getrulesmessage('')


    await interaction.response.send_message(messagesendnow)

@client.tree.command(name="load_match_history")
async def load_match_history(interaction: discord.Interaction, userid: str, num_matches: int):
    UserID=int(userid)
    if interaction.user.id not in APPROVED_IDS:
        await interaction.response.send_message("Sorry, you are not authorized to use this command.")
        return    # Load the ongoing match for the input UserID

    user_ongoing = load_ongoing(UserID)

    # Check if the user has an ongoing match
    if user_ongoing["opponent"] is not None:
        opponent_id = user_ongoing["opponent"]
        await interaction.response.send_message(f"UserID {UserID} has an ongoing match with UserID {opponent_id}.")
    else:
        await interaction.response.send_message(f"UserID {UserID} does not have any ongoing matches.")
    # Load match records from the file
    with open('match_record.json', 'r') as f:
        match_records = [json.loads(line) for line in f]

    # Filter matches that involved the input UserID
    user_matches = [match for match in match_records if UserID in match["player_ids"]]

    # Sort the matches by date_time_reported in descending order
    user_matches.sort(key=lambda x: x['date_time_reported'], reverse=True)

    # Get the last num_matches matches
    last_matches = user_matches[:num_matches]

    # Send the details of the last num_matches matches to the user
    for match in last_matches:
        await interaction.channel.send(f"Match Type: {match['match_type']}\n"
                                                f"Player IDs: {match['player_ids']}\n"
                                                f"Winner: {match['winner']}\n"
                                                f"Elo Change: {match['elochange']}\n"
                                                f"Date Time Reported: {match['date_time_reported']}")



@client.tree.command(name="change_elo")
async def change_elo(interaction: discord.Interaction, userid: str, elo_change: int):
    UserID=int(userid)
    # Check if the user is approved
    if interaction.user.id not in APPROVED_IDS:
        await interaction.response.send_message("Sorry, you are not authorized to use this command.")
        return

    # Load the Elo rating for the input UserID
    user_elo = load_elo(UserID)

    # Store the old Elo rating
    old_elo = user_elo["rating"]

    # Change the Elo rating by the input value
    user_elo["rating"] += elo_change

    # Save the new Elo rating
    save_elo(UserID, user_elo)

    await interaction.response.send_message(f"UserID {UserID}'s Elo rating has been changed by {elo_change}. The old Elo rating was {old_elo}, and the new Elo rating is {user_elo['rating']}.")



@client.tree.command(name="leaderboard")
@app_commands.choices(option=[
    app_commands.Choice(name='Elo', value='elo'),
    app_commands.Choice(name='Games', value='games')
])
async def leaderboard(interaction: discord.Interaction,option: app_commands.Choice[str	]):
    # Load all Elo ratings from the file
    with open('elo.json', 'r') as f:
        all_elo = json.load(f)
    if  option.value=='elo':
          sortkey="rating"
          eloout=True
    else:
       sortkey='total_games'
       eloout=False

    # Sort the players by Elo rating in descending order
    sorted_players = sorted(all_elo.items(), key=lambda x: x[1][sortkey], reverse=True)

    # Get the top 10 players
    top_10_players = sorted_players[:10]

    # Send the leaderboard to the user
    leaderboard = "Leaderboard:\n"
    for i, (user_id, user_elo) in enumerate(top_10_players, start=1):
        user = await client.fetch_user(int(user_id))
        if eloout==True:
          leaderboard += f"{i}. {user.name} - Elo: {int(user_elo['rating'])}, Total Games: {user_elo['total_games']}\n"
        else: 
          leaderboard += f"{i}. {user.name} - Total Games: {user_elo['total_games']}\n"

    await interaction.response.send_message(leaderboard)



@client.tree.command(name="leaderboard_dahv")
@app_commands.choices(option=[
    app_commands.Choice(name='Elo', value='elo'),
    app_commands.Choice(name='Games', value='games')
])
async def leaderboard_dahv(interaction: discord.Interaction,option: app_commands.Choice[str	]):
    # Load all Elo ratings from the file
    with open('elodahv.json', 'r') as f:
        all_elo = json.load(f)
    if  option.value=='elo':
          sortkey="rating"
          eloout=True
    else:
       sortkey='total_games'
       eloout=False

    # Sort the players by Elo rating in descending order
    sorted_players = sorted(all_elo.items(), key=lambda x: x[1][sortkey], reverse=True)

    # Get the top 10 players
    top_10_players = sorted_players[:10]

    # Send the leaderboard to the user
    leaderboard = "Dahvplays Leaderboard:\n"
    for i, (user_id, user_elo) in enumerate(top_10_players, start=1):
        user = await client.fetch_user(int(user_id))
        if eloout==True:
          leaderboard += f"{i}. {user.name} - Elo: {int(user_elo['rating'])}, Total Games: {user_elo['total_games']}\n"
        else: 
          leaderboard += f"{i}. {user.name} - Total Games: {user_elo['total_games']}\n"

    await interaction.response.send_message(leaderboard)



@client.tree.command(name="admin_reset_que")
async def admin_reset_que(interaction: discord.Interaction):
    # Check if the user is approved
    if interaction.user.id not in APPROVED_IDS:
        await interaction.response.send_message("Sorry, you are not authorized to use this command.")
        return   
    global player_queue
    global player_param_override
    player_queue = []
    player_param_override = []

@client.tree.command(name="admin_save_dahv_elo")
async def admin_save_dahv_elo(interaction: discord.Interaction):
    # Check if the user is approved
    if interaction.user.id not in APPROVED_IDS:
        await interaction.response.send_message("Sorry, you are not authorized to use this command.")
        return   
    # Get the current date
    current_date = datetime.now().strftime('%Y-%m-%d')
    original_file='elodahv.json'
    # Create new file name
    new_file = original_file.replace('.json', f'_{current_date}.json')

    # Copy the file
    os.system(f'copy {original_file} {new_file}')
    await interaction.response.send_message("File copied to "+new_file,file=discord.File(new_file))



@client.tree.command(name="admin_get_max_elo_increase")
async def admin_get_max_elo_increase(interaction: discord.Interaction):
    # Check if the user is approved
    if interaction.user.id not in APPROVED_IDS:
        await interaction.response.send_message("Sorry, you are not authorized to use this command.")
        return

    # Load the original Elo ratings
    with open('elodahv.json', 'r') as f:
        original_elo = json.load(f)

    # Get the most recent Elo copy file
    list_of_files = glob.glob('elodahv_*.json')  # * means all if need specific format then *.csv
    latest_file = max(list_of_files, key=os.path.getctime)

    with open(latest_file, 'r') as f:
        latest_elo = json.load(f)


    # Find the user with the largest increase in Elo
    max_increase = 0
    max_user = None
    for user_id, original_rating in original_elo.items():
        if user_id in latest_elo:
            increase = -latest_elo[user_id]["rating"]+original_rating["rating"]
            if increase > max_increase:
                max_increase = increase
                max_user = user_id
        else:
            increase =-900+original_rating["rating"]
            if increase > max_increase:
                max_increase = increase
                max_user = user_id           

    # Output the user with the largest increase in Elo
    if max_user is not None:
        winnerobj =await  client.fetch_user(max_user)

        await interaction.response.send_message(f"The user with the largest increase in Elo is {max_user}, {winnerobj.name} with an increase of {int(max_increase)}.")
        
    else:
        await interaction.response.send_message("No users have increased their Elo.")



@client.tree.command(name="queue_size")
async def queue_size(interaction: discord.Interaction):
    # Send the number of players in the queue to the user
    await interaction.response.send_message(f"There are currently {len(player_queue)} players in the queue.")


# =============================================================================
# Events and entry point
# =============================================================================

@client.event
async def on_ready():
    print(f'Logged in as {client.user} (ID: {client.user.id})')
    print('------')

if __name__ == "__main__":
    client.run(BOT_TOKEN)
