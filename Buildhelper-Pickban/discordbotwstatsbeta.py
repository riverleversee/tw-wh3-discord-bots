"""Buildhelper / Pickban Discord bot for TW WH3 land battles.

Numerically optimized pick/ban decision helper: enumerates valid picks and bans under
player constraints (unplayables, global bans, series history, must-include, avoid lists)
and returns optimal options with expected matchup outcomes from a win-rate matrix.

Also provides matchup build help (!MUhelp), MU matrix uploads, and faction win stats.
Expects buildhelp/<FAC1>/<FAC2>/buildtext.txt and optional IMAG*.jpg (see SOURCE.txt).
"""

import datetime
import io
import os
import shutil
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import discord
import numpy as np
import pandas as pd
import requests
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

# =============================================================================
# Constants and configuration
# =============================================================================

def _parse_id_list(value: str) -> list[int]:
    return [int(x.strip()) for x in value.split(",") if x.strip()]


BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]

CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])
REPORT_CHANNEL_ID = int(os.environ.get("DISCORD_REPORT_CHANNEL_ID", "0"))
ADMIN_USER_IDS = _parse_id_list(os.environ.get("DISCORD_ADMIN_USER_IDS", ""))
ROLE_IDS = _parse_id_list(os.environ["DISCORD_ROLE_IDS"])
ROLE_IDS_HELP_UPDATE = _parse_id_list(os.environ.get("DISCORD_ROLE_IDS_HELP_UPDATE", ""))
USER_IDS_HELP_UPDATE = _parse_id_list(os.environ.get("DISCORD_USER_IDS_HELP_UPDATE", "0"))
CLEARED_FOR_IMAGES = _parse_id_list(os.environ.get("DISCORD_USER_IDS_CLEARED_IMAGES", "0"))
MAX_SESSION_TIME_MINUTES = 100000000

#MUmatrixfilename="domMUmatrix.csv"
#df = pd.read_csv(MUmatrixfilename)
#MUsdom=pd.DataFrame(df).to_numpy()

totalsaves=0
maxsaves=40

roleids = ROLE_IDS
roleidshelpupdate = ROLE_IDS_HELP_UPDATE
useridshelpupdate = USER_IDS_HELP_UPDATE
clearedforimages = CLEARED_FOR_IMAGES

guild1_id = int(os.environ["DISCORD_GUILD_ID"])

MUmatrixfilename="MUmatrix.csv"
df = pd.read_csv(MUmatrixfilename)
MUslb=pd.DataFrame(df).to_numpy()
MUmatrixfilenamestrat="MUmatrixstrat.csv"
dfstrat = pd.read_csv(MUmatrixfilenamestrat)
MUslbstrat=pd.DataFrame(dfstrat).to_numpy()
statsupdateactive=False
allowedlang=['','ESP','ITL','ENG']

@dataclass
class Session:
    is_active: bool = False
    start_time: int = 0

intents = discord.Intents(messages=True, guilds=True,message_content=True)

bot = commands.Bot(command_prefix="!", intents=intents)
session = Session()

@bot.event
async def on_ready():
    print("Hello! Study bot is ready!")
    channel = bot.get_channel(CHANNEL_ID)
    await channel.send("Bot Connected. I will begin the robot revolution.")




factionacronymsdom=['BM','BR','CD','DC','DE','DW','EM','GC','GS','HE','KH','KI','LM','NR','NG','OK','SK','SL','TK','TZ','VP','VC','WC','WE']


factionacronyms=['BM','BR','CD','DE','DC','DW','EM','GC','GS','HE','KH','KS','LM','NG','NR','OK','SK','SL','TK','TZ','VC','VP','WE','WC']

# =============================================================================
# New player / MU help commands
# =============================================================================


class MUhelpflags(commands.FlagConverter):
        MU: str=''
        Mode: str=''
        LANG: str=''
        linenumber: str='1d'
        newline: str='NO LINE INPUT'
        newlinetype: str='Text'

def getfilepathstr(instr,factionslist,lang,mode,allowedlang):
    path=False
    pathfolder=False
    errorflag=0
    while instr[0]==' ' and len(instr)>6:
        instr=instr[1:len(instr)]
    while instr[len(instr)-1]==' ' and len(instr)>6:
        instr=instr[0:len(instr)-1]    
    if instr[len(instr)-1]==' ':
       errorflag=1
       return path,pathfolder,errorflag 
    if instr[len(instr)-1]==' ':
       errorflag=1
       return path,pathfolder,errorflag 
    fac1=instr[0:2].upper()
    found=False
    for i in range(len( factionslist)):
       if fac1==factionslist[i]:
          found=True
    if found==False:
       errorflag=2
       return path,pathfolder,errorflag 
    fac2=instr[4:6].upper()
    found2=False
    for i in range(len( factionslist)):
       if fac2==factionslist[i]:
          found2=True
    if found2==False:
       errorflag=3
       return path,pathfolder,errorflag 
    mode=mode.upper()
    if mode!='DOM' and mode!='' and mode!='LB':
       errorflag=4
       return path,pathfolder,errorflag 
    if mode!='DOM':
        mode=''
    else: 
      mode="DOM/"
    if lang!='':
       lang=lang+"/"
 
    path="buildhelp/"+lang+mode+fac1+"/"+""+fac2+'/'+"buildtext.txt"
    pathfolder="buildhelp/"+mode+fac1+"/"+""+fac2+'/'
    return path,pathfolder,errorflag 

@bot.command()
async def MUhelp(ctx,*,flags: MUhelpflags):
    global factionacronyms
    factionslist=factionacronyms[:]
    global allowedlang
    langin=flags.LANG
    modein=flags.Mode
    MUin=flags.MU
    langfound=False
    langindex=0
    for i in range(len(allowedlang)): 
         if langin.upper()==allowedlang[i].upper():
             langfound=True
             langindex=i
    if langindex==3:
       langindex=0
    if langfound==False:
        linenow='Language not recognized please select ENG, ESP, or ITL'
        await ctx.channel.send(linenow)
        return

    if MUin=='':
        linenow=['This is a bot to help players understand matchups and find builds. Input MU: AvsB (i.e. MU: GSvsHE) to get build advice.']
        await ctx.channel.send(linenow[langindex])
        return
    pathuse,pathfolder,errorcode=getfilepathstr(MUin,factionslist,langin,modein,allowedlang)
    if errorcode!=0:
       await ctx.channel.send('Error '+str(errorcode))
       await ctx.channel.send('Errors 1-3 correspond to problems parsing the specified factions. Error4 is an error in th game mode identification')
       return
    try:
     print(pathuse)
     print(pathfolder)

     fileMU=open(pathuse,'r')
     linesMU=fileMU.readlines()
     fileMU.close()
     for i in range(len(linesMU)):
        linenow=linesMU[i]
        if len(linenow)>=5:
         try:
          if linenow[0:5].upper()=='TEXT:'.upper():
             await ctx.channel.send(linenow[5:len(linenow)])
          if linenow[0:5].upper()=='IMAG:'.upper():
             splitline=linenow.split()
             pathimg=pathfolder+'IMAG'+str(i+1)+'.jpg'
             with open(pathimg, 'rb') as f:
                  picture = discord.File(f)
                  await ctx.channel.send(file=picture)
         except:
             print('couldnotsend')
    except:
            await ctx.channel.send('Not yet uploaded please try again later.')

    return

@bot.command()
async def MUhelpunfinished(ctx,*,flags: MUhelpflags):
    global factionacronyms
    factionslist=factionacronyms[:]
    global allowedlang
    langin=flags.LANG
    modein=flags.Mode
    MUin=flags.MU
    langfound=False
    langindex=0
    for i in range(len(allowedlang)): 
         if langin.upper()==allowedlang[i].upper():
             langfound=True
             langindex=i
    if langindex==3:
       langindex=0
    if langfound==False:
        linenow='Language not recognized please select ENG, ESP, or ITL'
        await ctx.channel.send(linenow)
        return
    
    if MUin=='':
        linenow=['This is a bot to help players understand matchups and find builds. Input MU: AvsB (i.e. MU: GSvsHE) to get build advice.']
        await ctx.channel.send(linenow[langindex])
        return
    
    Min=['']*len(factionslist)
    for i in range(len(factionslist)):
      MUinsplit=list(MUin)
      foundchar=0
      for j in range(len(MUinsplit)):
        if MUinsplit[j]!=' ':
          Min[i]+=MUinsplit[j]
          foundchar+=1
          if foundchar>1:
            break
      Min[i]+='vs'+factionslist[i]
      

    for MUnow in Min:
     try:

      pathuse,pathfolder,errorcode=getfilepathstr(MUnow,factionslist,langin,modein,allowedlang)
      if           errorcode!=0:
          await ctx.channel.send(MUnow+'Bad input chars.')
          return
      try: 
       fileMU=open(pathuse,'r')
       linesMU=fileMU.readlines()
       fileMU.close()
       for i in range(len(linesMU)):
        linenow=linesMU[i]
        if len(linenow)>=5:
         try:
          if linenow[0:5].upper()=='IMAG:'.upper():
             splitline=linenow.split()
             pathimg=pathfolder+'IMAG'+str(i+1)+'.jpg'
             with open(pathimg, 'rb') as f:
                  picture = discord.File(f)
         except:
             print('couldnotsend')
      except:
            await ctx.channel.send(MUnow+' Not yet uploaded.')

     except:
            await ctx.channel.send(MUnow+'Bad input chars.')

    return



@bot.command()
async def updateMUhelp(ctx,*,flags: MUhelpflags):
    global allowedlang
    global factionacronyms
    factionslist=factionacronyms
    langin=flags.LANG
    modein=flags.Mode
    MUin=flags.MU
    langfound=False
    langindex=0

    guild = bot.get_guild(guild1_id)
    try:
          member = await guild.fetch_member(ctx.author.id)


          for r in member.roles:
            for rolentry in roleids:
              if r.id == rolentry:
                 cleareduse=True
    except:
          cleareduse=False
    for idnow in useridshelpupdate:
      if ctx.author.id==idnow:
         cleareduse=True
    if cleareduse!=True:
        return 

    for i in range(len(allowedlang)): 
         if langin==allowedlang[i]:
             langfound=True
             langindex=i
    if langindex==3:
       langindex=0

    if langfound==False:
        linenow='Language not recognized please select ENG, ESP, or ITL'
        await ctx.channel.send(linenow)
        return

    if MUin=='':
        linenow=['This is a bot to help players understand matchups and find builds. Input AvsB (i.e. GSvsHE) to get build advice.']
        await ctx.channel.send(linenow[langindex])
        return
    pathuse,pathfolder,errorcode=getfilepathstr(MUin,factionslist,langin,modein,allowedlang)
    if errorcode!=0:
       await ctx.channel.send('Error'+str(errorcode))
       return
    linenumberin=flags.linenumber
    if linenumberin=='1d':
       linenumber=int(1)
       defaultline=True
    else: 
       linenumber=int(linenumberin)
       defaultline=False

    newline=flags.newline
    if len(newline)>2000:
            await ctx.channel.send('Newline Too Long')
            return

    newlinetype=flags.newlinetype


    if Path(pathuse).is_file()==False:
       openfile=open(pathuse,'w')
       baselines=['TEXT:\n','IMAG: 2\n']
       openfile.writelines(baselines)
       openfile.close()
    

    openfile=open(pathuse,'r')
    linesold=openfile.readlines()
    openfile.close()
    lineskeep=[' \n']*(len(linesold)+1)
    lineskeep[0:len(linesold)]=linesold[:]
    linesold=lineskeep
    print(linesold)
    if newlinetype.upper()=='Text'.upper() and newline!='NO LINE INPUT':
        splitnewline=newline.split('\n')
        
        linesnew=['']*(len(linesold)+len(splitnewline))
        if defaultline==True: 
                 linenumber=1

        for i in range(len(linesold)):
             if len(linesold[i])>=5 and i>=linenumber: 
                  if linesold[i][0:5]!='TEXT:':
                          linenotext=i
                          break
                  else: 
                          linenotext=i
                          break
        imagencounter=False
        imagencounters=-1*np.ones([10,2])
        imgfoun=0
        for i in range(linenumber-1):
            linesnew[i]=linesold[i]
        for i in range(len(splitnewline)):
            linesnew[i+linenumber-1]='TEXT:'+splitnewline[i]+'\n'
        for i in range(len(linesold)-linenotext):
              linenow=linesold[i+linenotext]
              if len(linenow)>=5:
                 if linenow[0:5].upper()=='IMAG:'.upper():
                   imagencounters[imgfoun,:]=np.array([i+len(splitnewline)+linenumber,i+linenotext+1])
                   imgfoun+=1
                   linesnew[i+len(splitnewline)+linenumber-1]='IMAG: '+str(int(i+len(splitnewline)+linenumber))+'\n'
                   imagencounter=True
                 else: 
                   linesnew[i+len(splitnewline)+linenumber-1]=linenow
        if imagencounter==True:
          try:

           for i in range(imgfoun): 
              infileimg= pathfolder + 'IMAG'+str(int(imagencounters[i,1]))+'.jpg'
              outfileimg= pathfolder + 'IMAG'+'TMP'+str(int(imagencounters[i,1]))+'.jpg'
              shutil.copyfile(infileimg, outfileimg,)


           for i in range(imgfoun):
               infileimg= pathfolder + 'IMAG'+'TMP'+str(int(imagencounters[i,1]))+'.jpg'
               outfileimg=pathfolder + 'IMAG'+str(int(imagencounters[i,0]))+'.jpg'
               shutil.copyfile(infileimg,outfileimg,)
               os.remove(infileimg)
          except: 
             print('no image')
        openfile=open(pathuse,'w')
        openfile.writelines(linesnew)
        openfile.close()
        await ctx.channel.send('Line updated')
    imageclear=False
    global clearedforimages
    for qq in range(len(clearedforimages)):
        if ctx.author.id==clearedforimages[qq]:
           imageclear=True
    if newlinetype.upper()=='IMAG' and imageclear:

        for attachment in ctx.message.attachments:
            if defaultline==True: 
                 for i in range(len(linesold)):
                    if len(linesold[i])>5: 
                       if linesold[i][0:5].upper()!='TEXT:'.upper():
                               linenumber=i+1
                               break
                    else: 
                               linenumber=i+1
                               break

            url= attachment.url
            discurlbase='https://cdn.discordapp.com/attachments/'
            urllist=list(url)
            discurlbaselist=list(discurlbase)
            for zz in range(len(discurlbaselist)):
                if discurlbaselist[zz]!=urllist[zz]:
                     await ctx.channel.send('Image URL not accepted')
                     return
            imageName = pathfolder + 'IMAG'+str(linenumber)+'.jpg'
            r = requests.get(url, stream=True)
            linesold[int(linenumber)-1]='IMAG: '+str(int(linenumber))+'\n'
            openfile=open(pathuse,'w')
            openfile.writelines(linesold)
            openfile.close()
            with open(imageName, 'wb') as out_file:
                      print('Saving image: ' + imageName)
                      shutil.copyfileobj(r.raw, out_file,)
            await ctx.channel.send('Image Updated')
    return




# =============================================================================
# Faction stats recording and output
# =============================================================================

class MUhelpflags(commands.FlagConverter):
        MU: str=''
        Mode: str=''
        LANG: str=''


def getfacsindex(instr,instr2,factionslist):

    outputstr=['','']
    outputindex=[-1,-1]
    errorflag=0
    
    splitstr=instr.split()
    outstr=''
    for i in range(len(splitstr)):
        outstr=outstr+splitstr[i].upper()

    splitstr2=instr2.split()
    outstr2=''
    for i in range(len(splitstr2)):
        outstr2=outstr2+splitstr2[i].upper()
    
    if len(outstr)<2 or len(outstr)>2 or len(outstr2)<2 or len(outstr2)>2:
        errorflag=1
        return outputstr,outputindex,errorflag 
       
     
    fac1=instr[:].upper()
    found=False
    for i in range(len( factionslist)):
       if fac1==factionslist[i]:
          found=True
          f1index=i


    winfac=instr2[:].upper()
    foundwin=False
    for i in range(len( factionslist)):
       if winfac==factionslist[i]:
          foundwin=True
          winfacindex=i
  
    if found==False or foundwin==False:
       errorflag=2
       return outputstr,outputindex,errorflag 

   
    outputstr[:]=[fac1,winfac]
    outputindex[:]=np.array([f1index,winfacindex])
     
    return outputstr,outputindex,errorflag 




class statsrecording(commands.FlagConverter):
        Loser: str=''
        Winner: str=''
        
        Remove: str=''



@bot.command()
async def updatestats(ctx,*,flags: statsrecording):
    global factionacronyms
    factionslist=factionacronyms
    
    winin=flags.Winner
    lostin=flags.Loser
    removeflag=flags.Remove
    if lostin=='' or winin=='':
        linenow=['This is a bot to help players record and see faction winrate statistics']
        await ctx.channel.send(linenow[0])
        return

    outputstr,outputindex,errorflag =getfacsindex(lostin,winin,factionslist)
    if errorflag!=0:
        await ctx.channel.send('error')
        return 
    global statsupdateactive
    
    loopswaiting=0
    while statsupdateactive==True:
       if loopswaiting==5:
           await ctx.channel.send('Please try to resubmit at a later time, the bot is currently updating statistics already')
           return
       time.sleep(5)
       loopswaiting=loopswaiting+1
    statsupdateactive=True
    
    oldname="factionstats/winstats.txt"
    
    winopen=open(oldname,'r')
    winlines=winopen.readlines()
    winopen.close()

    winlineedit=winlines[outputindex[1]].split()
    winlineeditval=int(winlineedit[outputindex[0]])
    
    
    splitstr=removeflag.split()
    removecheck=''
    for i in range(len(splitstr)):
        removecheck=removecheck+splitstr[i].upper()

    valflip=1
    if removecheck=='TRUE':
        valflip=-1
        
    winlineedit[outputindex[0]]=str(winlineeditval+valflip*1)
    
    winlinesave=winlineedit[0]
    for i in range(len(winlineedit)-1):
        winlinesave+=' '+winlineedit[i+1]
    winlinesave+='\n'
    winlines[outputindex[1]]=winlinesave

    winopen2=open(oldname,'w')
    winopen2.writelines(winlines)
    winopen2.close()
    statsupdateactive=False
    CHANNEL_IDreport = REPORT_CHANNEL_ID
    channel = bot.get_channel(CHANNEL_IDreport)
    authorid=ctx.author.id
    reportline="Game Reported by <@"+str(ctx.author.id)+"> for W: "+factionslist[outputindex[1]]+' L: '+factionslist[outputindex[0]]
    if valflip==-1:
        reportline="Game REMOVAL FROM STATS by <@"+str(ctx.author.id)+"> for W: "+factionslist[outputindex[1]]+' L: '+factionslist[outputindex[0]]
    await channel.send(reportline)
    await ctx.channel.send(reportline)
    return 
     



def processstats1fac(winarr,facindex):
    totalwin=np.zeros([len(winarr[:,0]),])
    
    totalwin[:]=winarr[facindex,:]
    totalloss=np.zeros([len(winarr[:,0]),])
    totalloss[:]=winarr[:,facindex]
    totalgame=np.ones([len(winarr[:,0]),2])
    totalgame[:,0]=totalwin[:]+totalloss[:]
    totalgametrue=np.max(totalgame,axis=1)
    
    winrate=np.round(totalwin[:]/totalgametrue[:]*100,decimals=1)
    overallwinrate=np.round(np.sum(totalwin[:])/np.max(np.array([np.sum(totalgame[:,0]),1]))*100,decimals=1)
    overalltotalgame=np.sum(totalgame[:,0])
    return winrate,totalgame[:,0],overallwinrate,overalltotalgame

def processstatsall(winarr):
    totalwin=np.zeros([len(winarr[:,0]),])
    totalwin[:]=np.sum(winarr[:,:],axis=1)
    
    totalloss=np.zeros([len(winarr[:,0]),])
        
    totalloss[:]=np.sum(winarr[:,:],axis=0)
    
    totalgame=np.ones([len(winarr[:,0]),2])
    totalgame[:,0]=totalwin[:]+totalloss[:]
    totalgametrue=np.max(totalgame,axis=1)
    
    
    winrate=np.round(totalwin[:]/totalgametrue[:]*100,decimals=1)
    return winrate,totalgame[:,0]


class statsoutput(commands.FlagConverter):
    faction: str=''

@bot.command()
async def factionstats(ctx,*,flags: statsoutput):
    global factionacronyms
    factionslist=factionacronyms
    facin=flags.faction
    
    if facin!='':
      splitstr=facin.split()
      facout=''
      for i in range(len(splitstr)):
        facout=facout+splitstr[i].upper()

      fac1=facout[:].upper()
      found=False
      for i in range(len( factionslist)):
         if fac1==factionslist[i]:
            found=True
            fac1index=i
            
      if found==False:
        await ctx.channel.send('Error')
   

    oldname="factionstats/winstats.txt"
    winopen=open(oldname,'r')
    winlines=winopen.readlines()
    winopen.close()
    numentries=len(winlines[0].split())
    winarr=np.zeros([numentries,numentries])
    
    for i in range( int(numentries)):
      winarr[int(i),0:int(numentries)]=np.array([float(x) for x in winlines[int(i)].split()])


    


    if facin=='':
        winrate,totalgame=processstatsall(winarr)
        printline='Overall Stats for all Factions\n'
        prefix=''
        printline+='Matchup: Winrate   Total Games\n'
    else:
        winrate,totalgame,overallwinrate,overalltotalgame=processstats1fac(winarr,fac1index)
        prefix=factionslist[fac1index]+'vs'
        printline='Overall stats for '+prefix+'\n'
        printline+='Matchup: Winrate   Total Games\n'
        
        
        printline+='All:                  '+str(overallwinrate)+'% \t    '+str(overalltotalgame)+'\n'

    for i in range(len(factionslist)):
        winstr=list(str(winrate[i]))
        winstrlen=len(winstr)
        totalstr=list(str(int(totalgame[i])))
        totalstrlen=len(totalstr)
        linenow=list('                         ')
        linenow[7-winstrlen:8]=winstr[:]
        linenow[8]='%\t'
        linenow[14-totalstrlen:15]=totalstr[:]
        linenow[18]=' \t |'

        lineprint=''.join(linenow)
        printline+=prefix+factionslist[i]+':      '+lineprint+'\n'
        
        if i==24:
             await ctx.channel.send(printline)
             printline=''
    
    
    await ctx.channel.send(printline)
    return 
    
class resetstatsflag(commands.FlagConverter):
        Saveold: str='emergencysave'

@bot.command()
async def resetstats(ctx,*,flags:  resetstatsflag):

    global factionacronyms
    factionslist=factionacronyms
    
    saveold=flags.Saveold
    cleareduse=False

    if ADMIN_USER_IDS and ctx.author.id in ADMIN_USER_IDS:
         cleareduse=True

    if cleareduse!=True:
       return
    oldname="factionstats/winstats.txt"
    newname="factionstats/winstats"+saveold+'.txt'
    Oldfile=open(oldname,'r')
    Newfile=open(newname,'w')
    Oldlines=Oldfile.readlines()
    Newfile.writelines(Oldlines)
    Newfile.close()
    Oldfile.close()
    Totalfactions=len(factionslist)
    Resetline='0'
    for i in range(Totalfactions-1):
         Resetline+=' 0'
    Resetline+='\n'
    print(Totalfactions)
    resetdoc=[Resetline]*Totalfactions
    Oldfile=open(oldname,'w')
    Oldfile.writelines(resetdoc)
    Oldfile.close()
    await ctx.channel.send('stats reset')
    return    


# =============================================================================
# Documentation / info commands
# =============================================================================
class infoflags(commands.FlagConverter):
    LANG: str=''

@bot.command()
async def info(ctx, *,flags: infoflags ):
    global allowedlang
    langin=flags.LANG
    langfound=False
    langindex=0
    for i in range(len(allowedlang)): 
         if langin.upper()==allowedlang[i].upper():
             langfound=True
             langindex=i
    if langindex==3:
       langindex=0
    if langfound==False:
        linenow='Language not recognized please select ENG, ESP, or ITL'
        await ctx.channel.send(linenow)
        return
    if langindex!=0:
         langpath=allowedlang[langindex].upper()+'/'
    else: 
         langpath=''
    print(langpath)
    print(langindex)
    print(langin)
    filenow='documentation/'+langpath+'info'+".txt"

    with io.open(filenow,'r', encoding='utf-8') as f: 
         alllinesnow=f.readlines()
         linesend=''
         for i in range(len(alllinesnow)): 
             linesnow=alllinesnow[i].split(r'\n')
             for j in range(len(linesnow)):
                 if len(linesend)+len(linesnow[j])>=1999:
                  
                    await ctx.send(linesend)
                    linesend=''
                 endchar='\n'
                 if j==len(linesnow)-1:
                     endchar=''
                 linesend=linesend+linesnow[j]+endchar
         await ctx.send(linesend)
                  

@bot.command()
async def infocounterpick3(ctx, *,flags: infoflags ):
    global allowedlang
    langin=flags.LANG
    langfound=False
    langindex=0
    for i in range(len(allowedlang)): 
         if langin.upper()==allowedlang[i].upper():
             langfound=True
             langindex=i
    if langindex==3:
       langindex=0
    if langfound==False:
        linenow='Language not recognized please select ENG, ESP, or ITL'
        await ctx.channel.send(linenow)
        return
    if langindex!=0:
         langpath=allowedlang[langindex].upper()+'/'
    else: 
         langpath=''
    filenow='documentation/'+langpath+'infocounterpick3'+".txt"


    with io.open(filenow,'r', encoding='utf-8') as f: 
         alllinesnow=f.readlines()
         linesend=''
         for i in range(len(alllinesnow)): 
             linesnow=alllinesnow[i].split(r'\n')
             for j in range(len(linesnow)):
                 if len(linesend)+len(linesnow[j])>=1999:
                  
                    await ctx.send(linesend)
                    linesend=''
                 endchar='\n'
                 if j==len(linesnow)-1:
                     endchar=''
                 linesend=linesend+linesnow[j]+endchar
         await ctx.send(linesend)


@bot.command()
async def infocounterpick2(ctx, *,flags: infoflags ):
    global allowedlang
    langin=flags.LANG
    langfound=False
    langindex=0    


    for i in range(len(allowedlang)): 
         if langin.upper()==allowedlang[i].upper():
             langfound=True
             langindex=i
    if langindex==3:
       langindex=0
    if langfound==False:
        linenow='Language not recognized please select ENG, ESP, or ITL'
        await ctx.channel.send(linenow)
        return
    if langindex!=0:
         langpath=allowedlang[langindex].upper()+'/'
    else: 
         langpath=''
    filenow='documentation/'+langpath+'infocounterpick2'+".txt"


    with io.open(filenow,'r', encoding='utf-8') as f: 
         alllinesnow=f.readlines()
         linesend=''
         for i in range(len(alllinesnow)): 
             linesnow=alllinesnow[i].split(r'\n')
             for j in range(len(linesnow)):
                 if len(linesend)+len(linesnow[j])>=1999:
                  
                    await ctx.send(linesend)
                    linesend=''
                 endchar='\n'
                 if j==len(linesnow)-1:
                     endchar=''
                 linesend=linesend+linesnow[j]+endchar
         await ctx.send(linesend)

@bot.command()
async def infopick3(ctx, *,flags: infoflags ):
    global allowedlang
    langin=flags.LANG

    langindex=0    

    langfound=False
    for i in range(len(allowedlang)): 
         if langin.upper()==allowedlang[i].upper():
             langfound=True
             langindex=i
    if langindex==3:
       langindex=0
    if langfound==False:
        linenow='Language not recognized please select ENG, ESP, or ITL'
        await ctx.channel.send(linenow)
        return
    if langindex!=0:
         langpath=allowedlang[langindex].upper()+'/'
    else: 
         langpath=''
    filenow='documentation/'+langpath+'infopick3'+".txt"


    with io.open(filenow,'r', encoding='utf-8') as f: 
         alllinesnow=f.readlines()
         linesend=''
         for i in range(len(alllinesnow)): 
             linesnow=alllinesnow[i].split(r'\n')
             for j in range(len(linesnow)):
                 if len(linesend)+len(linesnow[j])>=1999:
                  
                    await ctx.send(linesend)
                    linesend=''
                 endchar='\n'
                 if j==len(linesnow)-1:
                     endchar=''
                 linesend=linesend+linesnow[j]+endchar
         await ctx.send(linesend)

@bot.command()
async def infopick2(ctx, *,flags: infoflags ):
    global allowedlang
    langin=flags.LANG

    langindex=0    

    langfound=False
    for i in range(len(allowedlang)): 
         if langin.upper()==allowedlang[i].upper():
             langfound=True
             langindex=i
    if langindex==3:
       langindex=0
    if langfound==False:
        linenow='Language not recognized please select ENG, ESP, or ITL'
        await ctx.channel.send(linenow)
        return
    if langindex!=0:
         langpath=allowedlang[langindex].upper()+'/'
    else: 
         langpath=''
    filenow='documentation/'+langpath+'infopick2'+".txt"


    with io.open(filenow,'r', encoding='utf-8') as f: 
         alllinesnow=f.readlines()
         linesend=''
         for i in range(len(alllinesnow)): 
             linesnow=alllinesnow[i].split(r'\n')
             for j in range(len(linesnow)):
                 if len(linesend)+len(linesnow[j])>=1999:
                  
                    await ctx.send(linesend)
                    linesend=''
                 endchar='\n'
                 if j==len(linesnow)-1:
                     endchar=''
                 linesend=linesend+linesnow[j]+endchar
         await ctx.send(linesend)



@bot.command()
async def infopick1(ctx, *,flags: infoflags ):
    global allowedlang
    langin=flags.LANG

    langindex=0    

    langfound=False
    for i in range(len(allowedlang)): 
         if langin.upper()==allowedlang[i].upper():
             langfound=True
             langindex=i
    if langindex==3:
       langindex=0
    if langfound==False:
        linenow='Language not recognized please select ENG, ESP, or ITL'
        await ctx.channel.send(linenow)
        return
    if langindex!=0:
         langpath=allowedlang[langindex].upper()+'/'
    else: 
         langpath=''
    filenow='documentation/'+langpath+'infopick1'+".txt"


    with io.open(filenow,'r', encoding='utf-8') as f: 
         alllinesnow=f.readlines()
         linesend=''
         for i in range(len(alllinesnow)): 
             linesnow=alllinesnow[i].split(r'\n')
             for j in range(len(linesnow)):
                 if len(linesend)+len(linesnow[j])>=1999:
                  
                    await ctx.send(linesend)
                    linesend=''
                 endchar='\n'
                 if j==len(linesnow)-1:
                     endchar=''
                 linesend=linesend+linesnow[j]+endchar
         await ctx.send(linesend)



@bot.command()
async def infomatrixupload(ctx, *,flags: infoflags ):
    global allowedlang
    langin=flags.LANG
    langfound=False

    langindex=0    

    for i in range(len(allowedlang)): 
         if langin.upper()==allowedlang[i].upper():
             langfound=True
             langindex=i
    if langindex==3:
       langindex=0
    if langfound==False:
        linenow='Language not recognized please select ENG, ESP, or ITL'
        await ctx.channel.send(linenow)
        return
    if langindex!=0:
         langpath=allowedlang[langindex].upper()+'/'
    else: 
         langpath=''
    filenow='documentation/'+langpath+'infomatrixupload'+".txt"


    with io.open(filenow,'r', encoding='utf-8') as f: 
         alllinesnow=f.readlines()
         linesend=''
         for i in range(len(alllinesnow)): 
             linesnow=alllinesnow[i].split(r'\n')
             for j in range(len(linesnow)):
                 if len(linesend)+len(linesnow[j])>=1999:
                  
                    await ctx.send(linesend)
                    linesend=''
                 endchar='\n'
                 if j==len(linesnow)-1:
                     endchar=''
                 linesend=linesend+linesnow[j]+endchar
         await ctx.send(linesend)


@bot.command()
async def infoMUhelp(ctx, *,flags: infoflags ):
    global allowedlang
    langin=flags.LANG
    langfound=False

    langindex=0
    for i in range(len(allowedlang)): 
         if langin.upper()==allowedlang[i].upper():
             langfound=True
             langindex=i
    if langindex==3:
       langindex=0
    if langfound==False:
        linenow='Language not recognized please select ENG, ESP, or ITL'
        await ctx.channel.send(linenow)
        return
    if langindex!=0:
         langpath=allowedlang[langindex].upper()+'/'
    else: 
         langpath=''
    filenow='documentation/'+langpath+'infoMUhelp'+".txt"


    with io.open(filenow,'r', encoding='utf-8') as f: 
         alllinesnow=f.readlines()
         linesend=''
         for i in range(len(alllinesnow)): 
             linesnow=alllinesnow[i].split(r'\n')
             for j in range(len(linesnow)):
                 if len(linesend)+len(linesnow[j])>=1999:
                  
                    await ctx.send(linesend)
                    linesend=''
                 endchar='\n'
                 if j==len(linesnow)-1:
                     endchar=''
                 linesend=linesend+linesnow[j]+endchar
         await ctx.send(linesend)

@bot.command()
async def infoupdatestats(ctx, *,flags: infoflags ):
    global allowedlang
    langin=flags.LANG
    langfound=False
    langindex=0
    for i in range(len(allowedlang)): 
         if langin.upper()==allowedlang[i].upper():
             langfound=True
             langindex=i
    if langindex==3:
       langindex=0
    if langfound==False:
        linenow='Language not recognized please select ENG, ESP, or ITL'
        await ctx.channel.send(linenow)
        return
    if langindex!=0:
         langpath=allowedlang[langindex].upper()+'/'
    else: 
         langpath=''
    filenow='documentation/'+langpath+'infoupdatestats'+".txt"


    with io.open(filenow,'r', encoding='utf-8') as f: 
         alllinesnow=f.readlines()
         linesend=''
         for i in range(len(alllinesnow)): 
             linesnow=alllinesnow[i].split(r'\n')
             for j in range(len(linesnow)):
                 if len(linesend)+len(linesnow[j])>=1999:
                  
                    await ctx.send(linesend)
                    linesend=''
                 endchar='\n'
                 if j==len(linesnow)-1:
                     endchar=''
                 linesend=linesend+linesnow[j]+endchar
         await ctx.send(linesend)

@bot.command()
async def infofactionstats(ctx, *,flags: infoflags ):
    global allowedlang
    langin=flags.LANG
    langfound=False
    langindex=0
    for i in range(len(allowedlang)): 
         if langin.upper()==allowedlang[i].upper():
             langfound=True
             langindex=i
    if langindex==3:
       langindex=0
    if langfound==False:
        linenow='Language not recognized please select ENG, ESP, or ITL'
        await ctx.channel.send(linenow)
        return
    if langindex!=0:
         langpath=allowedlang[langindex].upper()+'/'
    else: 
         langpath=''
    filenow='documentation/'+langpath+'infofactionstats'+".txt"


    with io.open(filenow,'r', encoding='utf-8') as f: 
         alllinesnow=f.readlines()
         linesend=''
         for i in range(len(alllinesnow)): 
             linesnow=alllinesnow[i].split(r'\n')
             for j in range(len(linesnow)):
                 if len(linesend)+len(linesnow[j])>=1999:
                  
                    await ctx.send(linesend)
                    linesend=''
                 endchar='\n'
                 if j==len(linesnow)-1:
                     endchar=''
                 linesend=linesend+linesnow[j]+endchar
         await ctx.send(linesend)
@bot.command()
async def infoupdateMUhelp(ctx, *,flags: infoflags ):
    global allowedlang
    langin=flags.LANG
    langfound=False
    langindex=0
    for i in range(len(allowedlang)): 
         if langin.upper()==allowedlang[i].upper():
             langfound=True
             langindex=i
    if langindex==3:
       langindex=0
    if langfound==False:
        linenow='Language not recognized please select ENG, ESP, or ITL'
        await ctx.channel.send(linenow)
        return
    if langindex!=0:
         langpath=allowedlang[langindex].upper()+r'/'
    else: 
         langpath=''
    filenow='documentation/'+langpath+'infoupdateMUhelp'+".txt"


    with io.open(filenow,'r', encoding='utf-8') as f: 
         alllinesnow=f.readlines()
         linesend=''
         for i in range(len(alllinesnow)): 
             linesnow=alllinesnow[i].split(r'\n')
             for j in range(len(linesnow)):
                 if len(linesend)+len(linesnow[j])>=1999:
                  
                    await ctx.send(linesend)
                    linesend=''
                 endchar='\n'
                 if j==len(linesnow)-1:
                     endchar=''
                 linesend=linesend+linesnow[j]+endchar
         await ctx.send(linesend)
# =============================================================================
# Pick / ban aid commands
# =============================================================================
    
def parse(inlist,factionin): 
    dashes=0
    for q in inlist:
    	if q=='-':
    		dashes=dashes+1
    if len(inlist)>=1: 		
    	totalentries=dashes+1
    if len(inlist)==0: 		
    	totalentries=0    
    outlist=['']*totalentries
    entrynow=0
    for q in range(len(inlist)):
    	if inlist[q]=='-':
    		entrynow=entrynow+1
    	else:  
    		outlist[entrynow]=outlist[entrynow]+inlist[q]
    checkvalue=0
    for q in range(len(outlist)):
    	for k in range(len(factionin)):
    		if outlist[q]==factionin[k]:
    			checkvalue=checkvalue+1
    errorflag=0	
    if checkvalue!=len(outlist):
    	errorflag=1
    return [outlist, errorflag]



    



class Pick1Flags(commands.FlagConverter):
    usematrix: str=''
    unplayablefactions: list=[]
    opponentunplayablefactions: list=[]
    globalbans: list = []
    mustinclude: list=[]
    avoid: list=[]
    printlimit: int=15
    unbannable: list=[]
    bannumber: list=[3]
@bot.command()
async def infofactions(ctx ):
    stringnow=f"This is a command to list the allowed faction acronyms. The option usematrix: allows you to see the acronyms used (in order) for the MU matrix with the input name."
    await ctx.send(stringnow)  

class factionsflags(commands.FlagConverter):
    usematrix: str=''

@bot.command()
async def factions(ctx, *,flags: factionsflags ):
    if len(flags.usematrix)>0:
        facnamesopen=f"{flags.usematrix}"+".txt"

        if Path(facnamesopen).is_file()==False:
            await ctx.send(f"Could not find desired files please try reuploading them")       
            return 
        facfile=open(facnamesopen,'r')
        faclines=facfile.readlines()
        facfile.close()
        stringnow="The allowed faction acronyms for this matrix are:"+faclines[0]
    
        await ctx.send(stringnow)
    else:
        stringnow="The allowed default faction acronyms are: \n"f"['BM'=Beastmen, 'BR'=Bretonnia , 'CD'=Chaos Dwarfs, 'DE'=Dark Elves, 'DC'=Demons of Chaos, 'DW'=Dwarfs, 'EM'=Empire, 'GC'=Grand Cathay, 'GS'=Greenskins, 'HE'=High Elves, 'KH'=Khorne, 'KS'=Kislev, 'LM'=Lizardmen, 'NG'=Nurgle, 'NR'=Norsca, 'OK'=Ogre Kingdoms, 'SK'=Skaven, 'SL'=Slaanesh, 'TK'=Tomb Kings, 'TZ'=Tzeentch, 'VC'=Vampire Counts, 'VP'=Vampire Pirates, 'WE'=Wood Elves, 'WC'=Warriors of Chaos]"
    
        await ctx.send(stringnow)



class Pick3Flags(commands.FlagConverter):
        usematrix: str=''
        unplayablefactions: list=[]
        opponentunplayablefactions: list=[]
        globalbans: list = []
        bannumber: list=[1]
        mustinclude: list=[]
        avoid: list=[]
        printlimit: int=15
        unbannable: list=[]
        opponentunbannable: list=[]        
class Pick2Flags(commands.FlagConverter):
        usematrix: str=''
        unplayablefactions: list=[]
        opponentunplayablefactions: list=[]
        globalbans: list = []
        bannumber: list=[0]
        mustinclude: list=[]
        avoid: list=[]
        printlimit: int=15
        unbannable: list=[]
        opponentunbannable: list=[]     

@bot.command()
async def pick3(ctx,*,flags: Pick3Flags):
	
    if ctx.guild:
        await ctx.channel.send('This is not a DM, please DM the bot so it does not spam')
        return
    bans=int(flags.bannumber[0])
    printlimit=int(flags.printlimit)
    global MUslb
    global MUslbstrat


    cleareduse=False

    guild = bot.get_guild(guild1_id)
    try:
       member = await guild.fetch_member(ctx.author.id)


       for r in member.roles:
          for rolentry in roleids:
            if r.id == rolentry:
               cleareduse=True
    except:
        cleareduse=False
    if flags.usematrix=='' and cleareduse==False:
        MUs=np.zeros([len(MUslb[:,0]),len(MUslb[0,:])])
        
        MUs[:,:]=MUslb[:,:]
        factionacronymslb=['VP','VC','TK','WC','NR','BM','GS','SK','LM','DE','HE','WE','DW','EM','BR','KH','NG','SL','TZ','GC','KS','OK','CD']
        factionacronyms=['']*len(factionacronymslb)
        factionacronyms[:]=factionacronymslb[:]

    elif flags.usematrix=='' and cleareduse==True:
        MUs=np.zeros([len(MUslbstrat[:,0]),len(MUslbstrat[0,:])])

        MUs[:,:]=MUslbstrat[:,:]
        factionacronymslbstrat=['BM','BR','CD','DE','DC','DW','EM','GC','GS','HE','KH','KS','LM','NG','NR','OK','SK','SL','TK','TZ','VC','VP','WE','WC']
        
        factionacronyms=['']*len(factionacronymslbstrat)

        factionacronyms[:]=factionacronymslbstrat[:]

         
    else:
        Matrixfile=f"{flags.usematrix}"+".csv"
        facnamesopen=f"{flags.usematrix}"+".txt"

        if Path(Matrixfile).is_file()==False or Path(facnamesopen).is_file()==False:
            await ctx.send(f"Could not find desired files please try reuploading them")
        
            return 
        if Matrixfile==MUmatrixfilenamestrat and cleareduse==False:
            await ctx.send(f"You cannot access this file.")
        
            return            
        df = pd.read_csv(Matrixfile)
        MUs=pd.DataFrame(df).to_numpy()
        facfile=open(facnamesopen,'r')
        faclines=facfile.readlines()
        facfile.close()
        commacountfac=0
        for i in range(len(faclines[0])):
            if faclines[0][i]==',':
                commacountfac=1+commacountfac
        factionacronyms=['']*(commacountfac+1)
        k=0
        for i in range(len(faclines[0])):
            if faclines[0][i]==',':
                k=k+1
            else: 
                factionacronyms[k]=factionacronyms[k]+faclines[0][i]
                
    MUtemp=np.zeros([len(MUs[:,0]),len(MUs[0,:])])
    MUtemp[:,:]=MUs[:,:]
    MUcount=len(factionacronyms)
    counter=0
    for i in range(MUcount-2):
        for j in range(i+1,MUcount-1):
            for k in range(j+1,MUcount):
                counter=counter+1             
    [unplay,errorflagnow]=parse(flags.unplayablefactions,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.unplayablefactions}")
    	return
    [oppunplay,errorflagnow]=parse(flags.opponentunplayablefactions,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.opponentunplayablefactions}")    
    	return
    [globalsb,errorflagnow]=parse(flags.globalbans,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.globalbans}") 
    	return   
    [avoidfacs,errorflagnow]=parse(flags.avoid,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.avoid}")  
    	return  
    [includefacs,errorflagnow]=parse(flags.mustinclude,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.mustinclude}")    
    	return 
    [unban,errorflagnow]=parse(flags.unbannable,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.unbannable}")    
    	return
    [oppunban,errorflagnow]=parse(flags.opponentunbannable,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.opponentunbannable}")    
    	return    	
    	     	
    preban=oppunplay+globalsb
    allunplayable=unplay+globalsb

    if len(preban)>=1:
        prebanindex= [0] * (len(preban))
        
        for m in range(len(preban)):
            for n in range(len(factionacronyms)):
                if preban[m]==factionacronyms[n]:
                    prebanindex[m]=n    
        for m in range(len(preban)):
            MUtemp[:,int(prebanindex[m])]=10
    
    if len(allunplayable)>=1:
        allunplayableindex= [0] * (len(allunplayable))
        
        for m in range(len(allunplayable)):
            for n in range(len(factionacronyms)):
                if allunplayable[m]==factionacronyms[n]:
                    allunplayableindex[m]=n    
        for m in range(len(allunplayable)):
            MUtemp[int(allunplayableindex[m]),:]=-10
            
    if len(includefacs)>=1:
        includefacsindex= [0] * (len(includefacs))
        
        for m in range(len(includefacs)):
            for n in range(len(factionacronyms)):
                if includefacs[m]==factionacronyms[n]:
                    includefacsindex[m]=n     

    
    if len(avoidfacs)>=1:
        avoidfacsindex= [0] * (len(avoidfacs))
        
        for m in range(len(avoidfacs)):
            for n in range(len(factionacronyms)):
                if avoidfacs[m]==factionacronyms[n]:
                    avoidfacsindex[m]=n            
            
    if len(oppunban)>=1:
        oppunbanindex= [0] * (len(oppunban))
        
        for m in range(len(oppunban)):
            for n in range(len(factionacronyms)):
                if oppunban[m]==factionacronyms[n]:
                    oppunbanindex[m]=n
    if len(unban)>=1:
        unbanindex= [0] * (len(unban))
        
        for m in range(len(unban)):
            for n in range(len(factionacronyms)):
                if unban[m]==factionacronyms[n]:
                    unbanindex[m]=n     
                                   
    MUcount=len(factionacronyms)

    picksnow=np.zeros([3,MUcount])
    MUchoices=np.zeros([MUcount])
    MUchoicesindex=np.zeros([MUcount,3])    
    uselength=np.zeros([9,])
    faclength=np.zeros([counter,9,])
    yourfaction=np.zeros([counter,9,3*MUcount,])
    enemyfaction=np.zeros([counter,9,3*MUcount,])

    MUindexes=np.zeros([counter,9,3])
    invalidmus=0
    banlist=np.zeros([counter,9,2,bans,])
    sidednesslist=[-4 ,-3, -2, -1, 0,1,2,3,4]

    for i in range(MUcount-2):
            for j in range(i+1,MUcount-1):
                for k in range(j+1,MUcount):
                    picksnow[0,:]=MUtemp[i,:]
                    picksnow[1,:]=MUtemp[j,:]
                    picksnow[2,:]=MUtemp[k,:]
                    indexnow=[i,j,k]
                    for l in range(MUcount):
                    	MUchoicesindex[l,:]=np.argsort(picksnow[:,l])
                    	MUchoices[l]=picksnow[int(MUchoicesindex[l,1]),l]
      
                    if len(oppunban)>0:
                    	forcedMUsopp=np.zeros([len(oppunbanindex),4,])
                    	for l in range(MUcount):                    	
                    		for n in range(len(oppunbanindex)):
                    			if indexnow[int(MUchoicesindex[l,2])]==oppunbanindex[n] and picksnow[int(MUchoicesindex[l,2]),l]> picksnow[int(MUchoicesindex[l,1]),l]:
                    				forcedMUsopp[n,:]=[1,l,oppunbanindex[n],MUchoicesindex[l,2]]
                    				MUchoices[l]=picksnow[int(MUchoicesindex[l,2]),l]
                			
                        
                    Expectworstindex = np.argsort(MUchoices)

                    Expectworstvalue=MUchoices[Expectworstindex[bans]]   
                    
                    if len(oppunban)>0:
                    	oppforcedtrue=0
                    	for n in range(len(oppunbanindex)):
                    		if forcedMUsopp[n,0]==1 and forcedMUsopp[n,3]==Expectworstvalue:
                    			oppforcedtrue=1
                    			
                    	
                    		                       
                    
                    #Determines what the ban is and if it is flexible 
                    banflex=np.zeros([bans,])
                    banindex=np.zeros([bans,])
                    banshift=np.zeros([bans,])
                    for q in range(bans):
                    	banindex[q]=Expectworstindex[q]
                    	banshift[q]=q
                    	if MUchoices[int(banindex[q])]==Expectworstvalue:
                    		banflex[q]=1
                    
                    
                    forceoverall=0
                    if len(unban)>0:
                    	noneencountered=False
                    	forcedata=np.zeros([len(unbanindex),3,])
                    	forceoverall=0
                    	nonenecountered=True
                    	forcedata[:,1]=np.ones([len(unbanindex),])*Expectworstvalue
                    	for q in range(bans):
                    		for n in range(len(unbanindex)):
                    			for qq in range(bans):
                    				if banindex[q]==banindex[qq] and qq!=q:
                    					noneencountered=False
                    					if q>qq:
                    						banshift[q]=banshift[q]+1
                    						banindex[q]=Expectworstindex[int(banshift[q])]
                    					else: 
                    						banshift[qq]=banshift[qq]+1
                    						banindex[qq]=Expectworstindex[int(banshift[qq])]
                    			if banindex[q]==unbanindex[n]:
	                   				noneencountered=False
	                   				banshift[q]=banshift[q]+1
	                   				banindex[q]=Expectworstindex[int(banshift[q])]				        				
	                   				if Expectworstvalue > MUchoices[int(unbanindex[n])]:
	                   					Expectworstvalue = MUchoices[int(unbanindex[n])]
	                   					forceoverall=1
	                   					forcedata[n,0]=1
	                   					forcedata[n,1]=MUchoices[unbanindex[n]]
	                   					forcedata[n,2]=unbanindex[n]


                    			
                    	if np.min(forcedata[:,1])<Expectworstvalue:
                    	    		Expectworstvalue=np.min(forcedata[:,1])
#does this do anything?			    	

                    	for q in range(bans):
                    		if MUchoices[int(banindex[q])]>=Expectworstvalue:
                    			banflex[q]=1			    	
			  

		     	     
		
		    #if any factions are to be avoided this section ensures they are avoided
                    if len(avoidfacs)>=1:
                        encounters=np.zeros([len(avoidfacsindex),])
                        for n in range(len(avoidfacsindex)):                     
                        		if MUchoices[avoidfacsindex[n]]==Expectworstvalue:                                     
                                              encounters[n]=1
                                              if len(unban)>0:
                                              	for m in range(len(unbanindex)):
                                              		if avoidfacsindex[n]==unbanindex[m]:
                                              			Expectworstvalue=-10
                                              
                        if sum(encounters)>sum(banflex):
                        	Expectworstvalue=-10
                        elif sum(encounters)>0:
                        	for n in range(len(avoidfacsindex)):
                        		for q in range(bans):                        		
                        			if encounters[n]==1 and banflex[q]==1:
                        				banflex[q]=0
                        				banindex[q]=avoidfacsindex[n]
					
				 
			 	
                    
                    #if mustinclude is active this ensures that the included factions are present                                                          
                    
                    if len(includefacs)>=1:
                    	included=0
                   
                    	for n in range(len(includefacsindex)):
                    		if includefacsindex[n]==i or includefacsindex[n]==j or includefacsindex[n]==k:
                    			included=included+1
                    
                    	if included!=len(includefacsindex):
                    		Expectworstvalue=-10
                    		
                    #sorts out any MUs that contain an invalid faction		
                    for p in range(3):
                    	if np.sum(picksnow[p,:])==-10*len(picksnow[p,:]):
                    		Expectworstvalue=-10	
                    	
		    
                    
                    indexnow=[i,j,k]
                    for g in range(9):
                        if Expectworstvalue<-4:
                            invalidmus=invalidmus+1
                        if float(Expectworstvalue)==float(sidednesslist[g]):
                        
                            for l in range(MUcount):
                                if float(MUchoices[l])==float(sidednesslist[g]):
                                    for w in range(3):
                                        if float(picksnow[w,l])==float(sidednesslist[g]):                                          
                                            yourfaction[int(uselength[g]),g,int(faclength[int(uselength[g]),g])]=indexnow[w]
                                            enemyfaction[int(uselength[g]),g,int(faclength[int(uselength[g]),g])]=l
                                            faclength[int(uselength[g]),g]=faclength[int(uselength[g]),g]+1
                                            
                            MUindexes[int(uselength[g]),g,:]=[i,j,k]
                            banlist[int(uselength[g]),g,0,:]=banindex
                            banlist[int(uselength[g]),g,1,:]=banflex
                            if len(unban)>0 and forceoverall==1:
                            	yourfaction[int(uselength[g]),g,:]=np.zeros([3*MUcount,])
                            	enemyfaction[int(uselength[g]),g,:]=np.zeros([3*MUcount,])
                            	faclength[int(uselength[g]),g]=0
                            	for n in range(len(unbanindex)):
                            		if float(MUchoices[unbanindex[n]])==float(sidednesslist[g]):
                            			for w in range(3):
                            				if float(picksnow[w,unbanindex[n]])==float(sidednesslist[g]):
                            					yourfaction[int(uselength[g]),g,int(faclength[int(uselength[g]),g])]=indexnow[w]
                            					enemyfaction[int(uselength[g]),g,int(faclength[int(uselength[g]),g])]=n
                            					faclength[int(uselength[g]),g]=faclength[int(uselength[g]),g]+1
                                                    
                            uselength[g]=uselength[g]+1


    trigger=0                    
    for h in range(len(uselength)):
        r=len(uselength)-h-1
        if uselength[r]>0 and trigger<1:
            trigger=1
            for y in range(int(uselength[r])):
                orderlist=np.argsort(faclength[0:int(uselength[r]),r],0)
                if y>=printlimit:
                	await ctx.send(f"There were a total of {int(uselength[r])} total possible picks.  Printing stopped at the first {printlimit}."+ " To print more use the option printlimit: N to print N possible picks." )
                	break


                ynew=orderlist[y]
                fullsend=""
                fullsend=fullsend+f'Best MUs eveness: '+str(sidednesslist[r])+'\n'
                if bans>0:
                	fullsend=fullsend+f"Pick: {factionacronyms[int(MUindexes[ynew,r,0])]}, {factionacronyms[int(MUindexes[ynew,r,1])]}, { factionacronyms[int(MUindexes[ynew,r,2])]} Ban: "
                	for h in range(bans):
                		if banlist[ynew,r,1,h]==0:
                		    fullsend=fullsend+f" {factionacronyms[int(banlist[ynew,r,0,h])]},"
                		else:
                		    fullsend=fullsend+f"Any"
                	fullsend=fullsend+f"\n"
                                        	                	
                	
                if bans==0:
                	fullsend=fullsend+f"Pick: {factionacronyms[int(MUindexes[ynew,r,0])]}, {factionacronyms[int(MUindexes[ynew,r,1])]}, { factionacronyms[int(MUindexes[ynew,r,2])]} \n"
                fullsend=fullsend+f"Expected MUs are: \n"
                for x in range(int(faclength[ynew,r])):
                	fullsend=fullsend+f"{factionacronyms[int(yourfaction[ynew,r,x])]} vs {factionacronyms[int(enemyfaction[ynew,r,x])]}, "
                await ctx.send(fullsend)

    await ctx.send(f"End Results")
    return   



@bot.command()
async def pick1(ctx,*,flags: Pick1Flags):

        if ctx.guild:
            await ctx.channel.send('This is not a DM, please DM the bot so it does not spam')
            return
        bans=int(flags.bannumber[0])
        printlimit=int(flags.printlimit)
        global MUslb
        global MUslbstrat


        cleareduse=False
        guild = bot.get_guild(guild1_id)
        try:
          member = await guild.fetch_member(ctx.author.id)


          for r in member.roles:
            for rolentry in roleids:
              if r.id == rolentry:
                 cleareduse=True
        except:
          cleareduse=False
        if flags.usematrix=='' and cleareduse==False:
            MUs=np.zeros([len(MUslb[:,0]),len(MUslb[0,:])])
    
            MUs[:,:]=MUslb[:,:]
            factionacronymslb=['VP','VC','TK','WC','NR','BM','GS','SK','LM','DE','HE','WE','DW','EM','BR','KH','NG','SL','TZ','GC','KS','OK','CD']
            factionacronyms=['']*len(factionacronymslb)

            factionacronyms[:]=factionacronymslb[:]

        elif flags.usematrix=='' and cleareduse==True:
            MUs=np.zeros([len(MUslbstrat[:,0]),len(MUslbstrat[0,:])])

            MUs[:,:]=MUslbstrat[:,:]
            factionacronymslbstrat=['BM','BR','CD','DE','DC','DW','EM','GC','GS','HE','KH','KS','LM','NG','NR','OK','SK','SL','TK','TZ','VC','VP','WE','WC']

            factionacronyms=['']*len(factionacronymslbstrat)

            factionacronyms[:]=factionacronymslbstrat[:]

         
        else:
            Matrixfile=f"{flags.usematrix}"+".csv"
            facnamesopen=f"{flags.usematrix}"+".txt"

            if Path(Matrixfile).is_file()==False or Path(facnamesopen).is_file()==False:
                await ctx.send(f"Could not find desired files please try reuploading them")
        
                return 
            if Matrixfile==MUmatrixfilenamestrat and cleareduse==False:
                await ctx.send(f"You cannot access this file.")
        
                return            
            df = pd.read_csv(Matrixfile)
            MUs=pd.DataFrame(df).to_numpy()
            facfile=open(facnamesopen,'r')
            faclines=facfile.readlines()
            facfile.close()
            commacountfac=0
            for i in range(len(faclines[0])):
                if faclines[0][i]==',':
                    commacountfac=1+commacountfac
            factionacronyms=['']*(commacountfac+1)
            k=0
            for i in range(len(faclines[0])):
                if faclines[0][i]==',':
                    k=k+1
                else: 
                    factionacronyms[k]=factionacronyms[k]+faclines[0][i]
                        
        
        
        MUtemp=np.zeros([len(MUs[:,0]),len(MUs[0,:])])
        MUtemp[:,:]=MUs[:,:]
        MUcount=len(factionacronyms)
        counter=len(factionacronyms)

        [unplay,errorflagnow]=parse(flags.unplayablefactions,factionacronyms)
        if errorflagnow==1:
        	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.unplayablefactions}")
        	return
        [oppunplay,errorflagnow]=parse(flags.opponentunplayablefactions,factionacronyms)
        if errorflagnow==1:
        	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.opponentunplayablefactions}")    
        	return
        [globalsb,errorflagnow]=parse(flags.globalbans,factionacronyms)
        if errorflagnow==1:
        	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.globalbans}") 
        	return   
        [avoidfacs,errorflagnow]=parse(flags.avoid,factionacronyms)
        if errorflagnow==1:
        	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.avoid}")  
        	return  
        [includefacs,errorflagnow]=parse(flags.mustinclude,factionacronyms)
        if errorflagnow==1:
        	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.mustinclude}")    
        	return 
        [unban,errorflagnow]=parse(flags.unbannable,factionacronyms)
        if errorflagnow==1:
        	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.unbannable}")    
        	return
  	
        preban=oppunplay+globalsb
        allunplayable=unplay+globalsb

        if len(preban)>=1:
            prebanindex= [0] * (len(preban))
            
            for m in range(len(preban)):
                for n in range(len(factionacronyms)):
                    if preban[m]==factionacronyms[n]:
                        prebanindex[m]=n    
            for m in range(len(preban)):
                MUtemp[:,int(prebanindex[m])]=10
        
        if len(allunplayable)>=1:

            allunplayableindex= [0] * (len(allunplayable))
            
            for m in range(len(allunplayable)):
                for n in range(len(factionacronyms)):
                    if allunplayable[m]==factionacronyms[n]:
                        allunplayableindex[m]=n    
            for m in range(len(allunplayable)):
                MUtemp[int(allunplayableindex[m]),:]=-10

        if len(includefacs)>=1:
            includefacsindex= [0] * (len(includefacs))
            
            for m in range(len(includefacs)):
                for n in range(len(factionacronyms)):
                    if includefacs[m]==factionacronyms[n]:
                        includefacsindex[m]=n     

        
        if len(avoidfacs)>=1:
            avoidfacsindex= [0] * (len(avoidfacs))
            
            for m in range(len(avoidfacs)):
                for n in range(len(factionacronyms)):
                    if avoidfacs[m]==factionacronyms[n]:
                        avoidfacsindex[m]=n            
                

        if len(unban)>=1:
            unbanindex= [0] * (len(unban))
            
            for m in range(len(unban)):
                for n in range(len(factionacronyms)):
                    if unban[m]==factionacronyms[n]:
                        unbanindex[m]=n     
        
                               
        MUcount=len(factionacronyms)

        picksnow=np.zeros([MUcount])
        MUchoices=np.zeros([MUcount])
        MUchoicesindex=np.zeros([MUcount,3])    
        uselength=np.zeros([9,])
        faclength=np.zeros([counter,9,])
        yourfaction=np.zeros([counter,9,MUcount,])
        enemyfaction=np.zeros([counter,9,MUcount,])

        MUindexes=np.zeros([counter,9])
        invalidmus=0
        banlist=np.zeros([counter,9,2,bans,])
        sidednesslist=[-4 ,-3, -2, -1, 0,1,2,3,4]

        for i in range(MUcount):
            picksnow[:]=MUtemp[i,:]
            indexnow=i
            MUchoices[:]=picksnow[:]
    		


            Expectworstindex = np.argsort(MUchoices)

            Expectworstvalue=MUchoices[Expectworstindex[bans]]   
            
  
            		                       
            
            #Determines what the ban is and if it is flexible 
            banflex=np.zeros([bans,])
            banindex=np.zeros([bans,])
            banshift=np.zeros([bans,])
            for q in range(bans):
            	banindex[q]=Expectworstindex[q]
            	banshift[q]=q
            	if MUchoices[int(banindex[q])]==Expectworstvalue:
            		banflex[q]=1
            
            
            forceoverall=0
            if len(unban)>0:
            	noneencountered=False
            	forcedata=np.zeros([len(unbanindex),3,])
            	forceoverall=0
            	nonenecountered=True
            	forcedata[:,1]=np.ones([len(unbanindex),])*Expectworstvalue
            	for q in range(bans):
            		for n in range(len(unbanindex)):
            			for qq in range(bans):
            				if banindex[q]==banindex[qq] and qq!=q:
            					noneencountered=False
            					if q>qq:
            						banshift[q]=banshift[q]+1
            						banindex[q]=Expectworstindex[int(banshift[q])]
            					else: 
            						banshift[qq]=banshift[qq]+1
            						banindex[qq]=Expectworstindex[int(banshift[qq])]
            			if banindex[q]==unbanindex[n]:
	                   				noneencountered=False
	                   				banshift[q]=banshift[q]+1
	                   				banindex[q]=Expectworstindex[int(banshift[q])]				        				
	                   				if Expectworstvalue > MUchoices[int(unbanindex[n])]:
	                   					forceoverall=1
	                   					forcedata[n,0]=1
	                   					forcedata[n,1]=MUchoices[int(unbanindex[n])]
	                   					forcedata[n,2]=unbanindex[n]


            			
            	if np.min(forcedata[:,1])<Expectworstvalue:
            	    		Expectworstvalue=np.min(forcedata[:,1])
#does this do anything?			    	

            	for q in range(bans):
            		if MUchoices[int(banindex[q])]>=Expectworstvalue:
            			banflex[q]=1			    	
			  

		     	     
		
		    #if any factions are to be avoided this section ensures they are avoided
            if len(avoidfacs)>=1:
                encounters=np.zeros([len(avoidfacsindex),])
                for n in range(len(avoidfacsindex)):                     
                		if MUchoices[avoidfacsindex[n]]==Expectworstvalue:                                     
                                      encounters[n]=1
                                      if len(unban)>0:
                                      	for m in range(len(unbanindex)):
                                      		if avoidfacsindex[n]==unbanindex[m]:
                                      			Expectworstvalue=-10
                                      
                if sum(encounters)>sum(banflex):
                	Expectworstvalue=-10
                elif sum(encounters)>0:
                	for n in range(len(avoidfacsindex)):
                		for q in range(bans):                        		
                			if encounters[n]==1 and banflex[q]==1:
                				banflex[q]=0
                				banindex[q]=avoidfacsindex[n]
					
				 
			 	
            
            #if mustinclude is active this ensures that the included factions are present                                                          
            
            if len(includefacs)>=1:
            	included=0
           
            	for n in range(len(includefacsindex)):
            		if includefacsindex[n]==i:
            			included=included+1
            
            	if included!=len(includefacsindex):
            		Expectworstvalue=-10
            		
            #sorts out any MUs that contain an invalid faction		
            if np.sum(picksnow[:])==-10*len(picksnow[:]):
                Expectworstvalue=-10	
            	
		    
            
            indexnow=i
            for g in range(9):
                if Expectworstvalue<-4:
                    invalidmus=invalidmus+1
                if Expectworstvalue==sidednesslist[g]:
                
                    for l in range(MUcount):
                        if float(MUchoices[l])==float(sidednesslist[g]):
                                if float(picksnow[l])==float(sidednesslist[g]):                                   
                                    yourfaction[int(uselength[g]),g,int(faclength[int(uselength[g]),g])]=i
                                    enemyfaction[int(uselength[g]),g,int(faclength[int(uselength[g]),g])]=l
                                    faclength[int(uselength[g]),g]=faclength[int(uselength[g]),g]+1
                                    
                    MUindexes[int(uselength[g]),g]=i
                    banlist[int(uselength[g]),g,0,:]=banindex
                    banlist[int(uselength[g]),g,1,:]=banflex
                    if len(unban)>0 and forceoverall==1:
                    	yourfaction[int(uselength[g]),g,:]=np.zeros([MUcount,])
                    	enemyfaction[int(uselength[g]),g,:]=np.zeros([MUcount,])
                    	faclength[int(uselength[g]),g]=0
                    	for n in range(len(unbanindex)):
                    		if float(MUchoices[unbanindex[n]])==float(sidednesslist[g]):
                    				if float(picksnow[unbanindex[n]])==float(sidednesslist[g]):
                    					yourfaction[int(uselength[g]),g,int(faclength[int(uselength[g]),g])]=i
                    					enemyfaction[int(uselength[g]),g,int(faclength[int(uselength[g]),g])]=n
                    					faclength[int(uselength[g]),g]=faclength[int(uselength[g]),g]+1
                                            
                    uselength[g]=uselength[g]+1


        trigger=0                    
        for h in range(len(uselength)):
            r=len(uselength)-h-1
            if uselength[r]>0 and trigger<1:
                trigger=1
                for y in range(int(uselength[r])):
                    orderlist=np.argsort(faclength[0:int(uselength[r]),r],0)
                    if y>=printlimit:
                    	await ctx.send(f"There were a total of {int(uselength[r])} total possible picks.  Printing stopped at the first {printlimit}."+ " To print more use the option printlimit: N to print N possible picks." )
                    	break


                    ynew=orderlist[y]
                    fullsend=""
                    fullsend=fullsend+f'Best MUs eveness: '+str(sidednesslist[r])+'\n'
                    if bans>0:
                        fullsend=fullsend+f"Pick: {factionacronyms[int(MUindexes[ynew,r])]} and \nBan:"
                        for h in range(bans):
                            if banlist[ynew,r,1,h]==0:
                                fullsend=fullsend+f" {factionacronyms[int(banlist[ynew,r,0,h])]},"
                            else:
                                fullsend=fullsend+f"Any"
                        fullsend=fullsend+f"\n"
                        	
                    if bans==0:
                    	fullsend=fullsend+f"Pick: {factionacronyms[int(MUindexes[ynew,r])]}\n"
                    fullsend=fullsend+f"Expected MUs are: \n"
                    for x in range(int(faclength[ynew,r])):
                    	fullsend=fullsend+f"{factionacronyms[int(yourfaction[ynew,r,x])]} vs {factionacronyms[int(enemyfaction[ynew,r,x])]}, "
                    await ctx.send(fullsend)

        await ctx.send(f"End Results")
        return   
        
class MatrixFlags(commands.FlagConverter):
    MatrixName: str=''
    Matrix: list=[]
    factionslist: list=[]



@bot.command()
async def matrixupload(ctx,*,flags: MatrixFlags):
    global totalsaves
    global maxsaves
    if totalsaves>=maxsaves:
        stringnow="Not currently accepting more uploads, either the bot was too popular today or someone tried to break it. Please contact a server admin to reset the bot."
        await ctx.send(stringnow) 

        return
    print(ctx.author.id)
    if flags.MatrixName=='':
        stringnow="You must include a name using MatrixName:, if the name is already in use or if someone later chooses the same name it might be overwritten. \n Choose a unique name to prevent overwriting other names"
        
        await ctx.send(stringnow) 
        return
    if (flags.MatrixName=='MUmatrix' or flags.MatrixName=='MUmatrixstrat') and ADMIN_USER_IDS and ctx.author.id not in ADMIN_USER_IDS:
        stringnow="Please choose a different name"
        await ctx.send(stringnow) 

        return
    #ensures the matrix has only allowed chars and has commas
    matinlist=flags.Matrix
    if len(matinlist)>0:
        for i in range(len(matinlist)):
            if matinlist[i]!='-' and matinlist[i]!=',' and matinlist[i].isnumeric()==False and matinlist[i]!='\n' :
                    stringnow="Format has unacceptable characters, please only have -, numbers, and commas."
                    await ctx.send(stringnow)            
                    return
        disttocom=0

        for i in range(len(matinlist)):
            disttocom=disttocom+1
            if matinlist[i]==',':
                    disttocom=0
            if disttocom>5:
                stringnow="Format is unacceptable, not enough commas."
                await ctx.send(stringnow) 
                return
        if len(matinlist)>26*26*2:
            stringnow="matrix list is too long"
            await ctx.send(stringnow)            
            return
            
                
                
    
#ensures the name only contains allowed chars            
    namein=flags.MatrixName
    allowedchar=['_','q','w','e','r','t','y','u','i','o','p','a','s','d','f','g','h','j','k','l','z','x','c','v','b','n','m','Q','W','E','R','T','Y','U','I','O','P','A','S','D','F','G','H','J','K','L','Z','X','C','V','B','N','M']
    allowedtotal=0
    for i in range(len(namein)):
        for j in range(len(allowedchar)):
            if namein[i]==allowedchar[j]:
                allowedtotal=allowedtotal+1
                break
    if allowedtotal!=len(namein): 
        stringnow=f"Format for your name has unacceptable characters, please only use letters and _. The registered input was {namein}"
        await ctx.send(stringnow)            
        return    
    allowedtotalfac=0
    allowedcharfac=[',','"',"'",'q','w','e','r','t','y','u','i','o','p','a','s','d','f','g','h','j','k','l','z','x','c','v','b','n','m','Q','W','E','R','T','Y','U','I','O','P','A','S','D','F','G','H','J','K','L','Z','X','C','V','B','N','M']
    if len(namein)>15:
        stringnow=f"Name is too long the registered input was {namein}"
        await ctx.send(stringnow)            
        return     
    if len(flags.factionslist)>0:
        factionsin=flags.factionslist
        for i in range(len(factionsin)):
            for j in range(len(allowedcharfac)):
                if factionsin[i]==allowedcharfac[j]:
                    allowedtotalfac=allowedtotalfac+1

        if allowedtotalfac!=len(factionsin): 
            stringnow=f"Format for factions list has unacceptable characters, please only use letters and _. The registered input was {factionsin}."
            await ctx.send(stringnow)            
            return     
        if len(factionsin)>5*26:
            stringnow="Factions list is too long, please use short names ~3 characters."
            await ctx.send(stringnow)            
            return
        #makes sure factions has enough commas 
        disttocomfac=0
        for i in range(len(factionsin)):
            disttocomfac=disttocomfac+1
            if factionsin[i]==',':
                    disttocomfac=0
            if disttocomfac>5:
                stringnow="Format is unacceptable, please choose shorter acronyms."
                await ctx.send(stringnow)                
                return
    
    if len(matinlist)>0:
        commacount=0
        for i in range(len(matinlist)):
            if matinlist[i]==',':
                commacount=1+commacount
            if matinlist[i]=='\n':
                break
        if commacount==22:
            basename='MUmatrix.csv'
        if commacount==23:
            basename='domMUmatrix.csv'
        if commacount<22 or commacount>23:
            stringnow="Format is unacceptable, too many commas."
            await ctx.send(stringnow)     
            return
    
            
        MUmatrixfilename=str(namein)+'.csv'
        filenew = open(MUmatrixfilename,'w')
        
        k=1
        linessaved=['']*(commacount+2)
        for i in range(commacount):
            linessaved[0]=linessaved[0]+','
        linessaved[0]=linessaved[0]+'\n'
        
        for j in range(len(matinlist)):
            linessaved[k]=linessaved[k]+matinlist[j]
            if matinlist[i]=='\n':
                k=k+1
        
        filenew.writelines(linessaved)
        filenew.close()
        stringnow=f"Matrix stored as {namein}"
        await ctx.send(stringnow)  

        totalsaves=totalsaves+1
        
        

    if len(flags.factionslist)>0:
        factionsin
        commacountfac=0
        for i in range(len(factionsin)):
            if factionsin[i]==',':
                commacountfac=1+commacountfac
        if commacountfac<22 or commacountfac>23:
            stringnow=f"Not enough entries or too many entries for factions"
            await ctx.send(stringnow) 
            return
                
        facfilename=str(namein)+'.txt'
        filenewfac = open(facfilename,'w')
        linessavedfac=''
        for i in range(len(factionsin)):
            linessavedfac=linessavedfac+factionsin[i]
        
        
        filenewfac.writelines(linessavedfac)
        filenewfac.close()
        stringnow=f"faction list stored as {namein}"
        await ctx.send(stringnow)    
        totalsaves=totalsaves+1
    print(totalsaves)
    return    
   
    
   

class CounterPick3Flags(commands.FlagConverter):
        usematrix: str=''
        unplayablefactions: list=[]
        opponentunplayablefactions: list=[]
        globalbans: list = []
        bannumber: list=[0]
        mustinclude: list=[]
        avoid: list=[]
        printlimit: int=15
        banned: list=[]
        picked: list=[]
        unbannable: list=[]
        opponentunbannable: list=[]  
        
        
@bot.command()
async def counterpick3(ctx,*,flags: CounterPick3Flags):
	
    if ctx.guild:
        await ctx.channel.send('This is not a DM, please DM the bot so it does not spam')
        return
    bans=int(flags.bannumber[0])
    printlimit=int(flags.printlimit)
    global MUslb
    global MUslbstrat


    cleareduse=False
    guild = bot.get_guild(guild1_id)
    try:
          member = await guild.fetch_member(ctx.author.id)


          for r in member.roles:
            for rolentry in roleids:
              if r.id == rolentry:
                 cleareduse=True
    except:
          cleareduse=False
    if flags.usematrix=='' and cleareduse==False:
        MUs=np.zeros([len(MUslb[:,0]),len(MUslb[0,:])])

        MUs[:,:]=MUslb[:,:]
        factionacronymslb=['VP','VC','TK','WC','NR','BM','GS','SK','LM','DE','HE','WE','DW','EM','BR','KH','NG','SL','TZ','GC','KS','OK','CD']
        factionacronyms=['']*len(factionacronymslb)

        factionacronyms[:]=factionacronymslb[:]

    elif flags.usematrix=='' and cleareduse==True:
        MUs=np.zeros([len(MUslbstrat[:,0]),len(MUslbstrat[0,:])])

        MUs[:,:]=MUslbstrat[:,:]
        factionacronymslbstrat=['BM','BR','CD','DE','DC','DW','EM','GC','GS','HE','KH','KS','LM','NG','NR','OK','SK','SL','TK','TZ','VC','VP','WE','WC']

        factionacronyms=['']*len(factionacronymslbstrat)

        factionacronyms[:]=factionacronymslbstrat[:]

         
    else:
        Matrixfile=f"{flags.usematrix}"+".csv"
        facnamesopen=f"{flags.usematrix}"+".txt"

        if Path(Matrixfile).is_file()==False or Path(facnamesopen).is_file()==False:
            await ctx.send(f"Could not find desired files please try reuploading them")
        
            return 
        if Matrixfile==MUmatrixfilenamestrat and cleareduse==False:
            await ctx.send(f"You cannot access this file.")
        
            return            
        df = pd.read_csv(Matrixfile)
        MUs=pd.DataFrame(df).to_numpy()
        facfile=open(facnamesopen,'r')
        faclines=facfile.readlines()
        facfile.close()
        commacountfac=0
        for i in range(len(faclines[0])):
            if faclines[0][i]==',':
                commacountfac=1+commacountfac
        factionacronyms=['']*(commacountfac+1)
        k=0
        for i in range(len(faclines[0])):
            if faclines[0][i]==',':
                k=k+1
            else: 
                factionacronyms[k]=factionacronyms[k]+faclines[0][i]
                                
    MUtemp=np.zeros([len(MUs[:,0]),len(MUs[0,:])])
    MUtemp[:,:]=-1*np.transpose(MUs[:,:])
    MUcount=len(factionacronyms)
    counter=0
    for i in range(MUcount-2):
        for j in range(i+1,MUcount-1):
            for k in range(j+1,MUcount):
                counter=counter+1             
    [ oppunplay,errorflagnow]=parse(flags.unplayablefactions,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.unplayablefactions}")
    	return
    [picked,errorflagnow]=parse(flags.picked,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.picked}")
    	return
    [banned,errorflagnow]=parse(flags.banned,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.banned}")
    	return
    [unplay,errorflagnow]=parse(flags.opponentunplayablefactions,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.opponentunplayablefactions}")    
    	return
    [globalsb,errorflagnow]=parse(flags.globalbans,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.globalbans}") 
    	return   
    [avoidfacs,errorflagnow]=parse(flags.avoid,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.avoid}")  
    	return  
    [includefacs,errorflagnow]=parse(flags.mustinclude,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.mustinclude}")    
    	return 
    [ oppunban,errorflagnow]=parse(flags.unbannable,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.unbannable}")    
    	return
    [ unban,errorflagnow]=parse(flags.opponentunbannable,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.opponentunbannable}")    
    	return    	
    	     	
    preban=oppunplay+globalsb+banned
    allunplayable=unplay+globalsb

    if len(preban)>=1:
        prebanindex= [0] * (len(preban))
        
        for m in range(len(preban)):
            for n in range(len(factionacronyms)):
                if preban[m]==factionacronyms[n]:
                    prebanindex[m]=n    
        for m in range(len(preban)):
            MUtemp[:,int(prebanindex[m])]=10
    
    if len(allunplayable)>=1:
        allunplayableindex= [0] * (len(allunplayable))
        
        for m in range(len(allunplayable)):
            for n in range(len(factionacronyms)):
                if allunplayable[m]==factionacronyms[n]:
                    allunplayableindex[m]=n    
        for m in range(len(allunplayable)):
            MUtemp[int(allunplayableindex[m]),:]=-10
            
    if len(includefacs)>=1:
        includefacsindex= [0] * (len(includefacs))
        
        for m in range(len(includefacs)):
            for n in range(len(factionacronyms)):
                if includefacs[m]==factionacronyms[n]:
                    includefacsindex[m]=n     

    
    if len(avoidfacs)>=1:
        avoidfacsindex= [0] * (len(avoidfacs))
        
        for m in range(len(avoidfacs)):
            for n in range(len(factionacronyms)):
                if avoidfacs[m]==factionacronyms[n]:
                    avoidfacsindex[m]=n            
            
    if len(oppunban)>=1:
        oppunbanindex= [0] * (len(oppunban))
        
        for m in range(len(oppunban)):
            for n in range(len(factionacronyms)):
                if oppunban[m]==factionacronyms[n]:
                    oppunbanindex[m]=n
    if len(unban)>=1:
        unbanindex= [0] * (len(unban))
        
        for m in range(len(unban)):
            for n in range(len(factionacronyms)):
                if unban[m]==factionacronyms[n]:
                    unbanindex[m]=n     
    pickedindex= [0] * (len(picked))
    
    for m in range(len(picked)):
        for n in range(len(factionacronyms)):
            if picked[m]==factionacronyms[n]:
                pickedindex[m]=n
    if len(pickedindex)!=3:
    	await ctx.send(f"Error, the command did not recognize 3 factions as the input from {picked}.") 
    	return
        
    if len(banned)>=1:
        bannedindex= [0] * (len(banned))
        
        for m in range(len(banned)):
            for n in range(len(factionacronyms)):
                if banned[m]==factionacronyms[n]:
                    bannedindex[m]=n                                   
    MUcount=len(factionacronyms)

    picksnow=np.zeros([3,MUcount])
    MUchoices=np.zeros([MUcount])
    oppban=np.zeros([MUcount])
    MUchoicesindex=np.zeros([MUcount,3])    


    MUindexes=np.zeros([counter,9,3])
    invalidmus=0
    banlist=np.zeros([counter,9,2,bans,])
    sidednesslist=[-4 ,-3, -2, -1, 0,1,2,3,4]
    
    
    picksnow[0,:]=MUtemp[pickedindex[0],:]
    picksnow[1,:]=MUtemp[pickedindex[1],:]
    picksnow[2,:]=MUtemp[pickedindex[2],:]
    indexnow=pickedindex
    for l in range(MUcount):
    	MUchoicesindex[l,:]=np.argsort(picksnow[:,l])
    	MUchoices[l]=picksnow[int(MUchoicesindex[l,1]),l]
    	oppban[l]=indexnow[int(MUchoicesindex[l,2])]
    oppbanflexnow=np.zeros([MUcount,])    
    if len(oppunban)>0:
    	forcedMUsopp=np.zeros([len(oppunbanindex),4,])
    	for l in range(MUcount):                    	
    		for n in range(len(oppunbanindex)):
    			if indexnow[int(MUchoicesindex[l,2])]==oppunbanindex[n] and picksnow[int(MUchoicesindex[l,2]),l]> picksnow[int(MUchoicesindex[l,1]),l]:
    				forcedMUsopp[n,:]=[1,l,oppunbanindex[n],MUchoicesindex[l,2]]
    				MUchoices[l]=picksnow[int(MUchoicesindex[l,2]),l]
    				oppbanflexnow[l]=1


    Expectworstindex = np.argsort(MUchoices)

    Expectworstvalue=MUchoices[Expectworstindex[bans]]   
    
    if len(oppunban)>0:
    	oppforcedtrue=0
    	for n in range(len(oppunbanindex)):
    		if forcedMUsopp[n,0]==1 and forcedMUsopp[n,3]==Expectworstvalue:
    			oppforcedtrue=1
    			
    	
    		                       
    
    #Determines what the ban is and if it is flexible 
    banflex=np.zeros([bans,])
    banindex=np.zeros([bans,])
    banshift=np.zeros([bans,])
    for q in range(bans):
    	banindex[q]=Expectworstindex[q]
    	banshift[q]=q
    	if MUchoices[int(banindex[q])]==Expectworstvalue:
    		banflex[q]=1
    
    
    forceoverall=0

		     	     
		
		    #if any factions are to be avoided this section ensures they are avoided
    if len(avoidfacs)>=1:
        encounters=np.zeros([len(avoidfacsindex),])
        for n in range(len(avoidfacsindex)):                     
        		if MUchoices[avoidfacsindex[n]]==Expectworstvalue:                                     
                              encounters[n]=1
                              if len(unban)>0:
                              	for m in range(len(unbanindex)):
                              		if avoidfacsindex[n]==unbanindex[m]:
                              			Expectworstvalue=-10
                              
        if sum(encounters)>sum(banflex):
        	Expectworstvalue=-10
        elif sum(encounters)>0:
        	for n in range(len(avoidfacsindex)):
        		for q in range(bans):                        		
        			if encounters[n]==1 and banflex[q]==1:
        				banflex[q]=0
        				banindex[q]=avoidfacsindex[n]
					
				 
			 	
    
    #if mustinclude is active this ensures that the included factions are present                                                          
    
    if len(includefacs)>=1:
    	included=0
   
    	for n in range(len(includefacsindex)):
    		if includefacsindex[n]==i or includefacsindex[n]==j or includefacsindex[n]==k:
    			included=included+1
    
    	if included!=len(includefacsindex):
    		Expectworstvalue=-10
    		
    #sorts out any MUs that contain an invalid faction		
    for p in range(3):
    	if np.sum(picksnow[p,:])==-10*len(picksnow[p,:]):
    		Expectworstvalue=-10	
    	
		    
    uselength=np.zeros([MUcount,])
    faclength=np.zeros([MUcount,])
    faclength=np.zeros([MUcount,])

    yourfaction=np.zeros([MUcount,3,])
    enemyfaction=np.zeros([MUcount,])    
    banfaction=np.zeros([MUcount,])    
    oppbanflex=np.zeros([MUcount,])    
    for l in range(MUcount):
      if picksnow[int(MUchoicesindex[l,2]),l]==picksnow[int(MUchoicesindex[l,1]),l]:
          oppbanflexnow[l]=1
        
    countfactions=0
    for l in range(MUcount):
        if float(MUchoices[l])==float(Expectworstvalue):
            for w in range(3):
                if float(picksnow[w,l])==float(Expectworstvalue):                                          
                    yourfaction[countfactions,int(faclength[countfactions])]=indexnow[w]
                    enemyfaction[countfactions]=l
                    faclength[countfactions]=faclength[countfactions]+1
                    banfaction[countfactions]=oppban[l]
                    oppbanflex[countfactions]=oppbanflexnow[l]
            countfactions=countfactions+1
                    
                    


    for y in range(int(countfactions)):
        orderlist=np.argsort(faclength[0:countfactions],0)
        if y>=printlimit:
        	await ctx.send(f"There were a total of {int(countfactions)} total possible picks.  Printing stopped at the first {printlimit}."+ " To print more use the option printlimit: N to print N possible picks." )
        	break
    
    
        ynew=orderlist[y]
        fullsend=""
        fullsend=fullsend+f'Best MUs eveness: '+str(-1*Expectworstvalue)+'\n'

                                	                	
        	
        fullsend=fullsend+f"Pick: {factionacronyms[int( enemyfaction[ynew])]}\n"
        if oppbanflex[ynew]==1:
            fullsend=fullsend+f"Ban: Any\n"
        else:
            fullsend=fullsend+f"Ban: {factionacronyms[int(banfaction[ynew])]}\n"
        fullsend=fullsend+f"Expected MUs are: \n"
        for x in range(int(faclength[ynew])):
        	fullsend=fullsend+f"{factionacronyms[int( enemyfaction[ynew])]} vs {factionacronyms[int( yourfaction[ynew,x])]}, "
        await ctx.send(fullsend)

    await ctx.send(f"End Results")
    return   



@bot.command()
async def pick2(ctx,*,flags: Pick2Flags):
	
    if ctx.guild:
        await ctx.channel.send('This is not a DM, please DM the bot so it does not spam')
        return
    bans=int(flags.bannumber[0])
    printlimit=int(flags.printlimit)
    global MUslb
    global MUslbstrat


    cleareduse=False
    guild = bot.get_guild(guild1_id)
    try:
          member = await guild.fetch_member(ctx.author.id)


          for r in member.roles:
            for rolentry in roleids:
              if r.id == rolentry:
                 cleareduse=True
    except:
          cleareduse=False

    if flags.usematrix=='' and cleareduse==False:
        MUs=np.zeros([len(MUslb[:,0]),len(MUslb[0,:])])

        MUs[:,:]=MUslb[:,:]
        factionacronymslb=['VP','VC','TK','WC','NR','BM','GS','SK','LM','DE','HE','WE','DW','EM','BR','KH','NG','SL','TZ','GC','KS','OK','CD']
        factionacronyms=['']*len(factionacronymslb)

        factionacronyms[:]=factionacronymslb[:]

    elif flags.usematrix=='' and cleareduse==True:
        MUs=np.zeros([len(MUslbstrat[:,0]),len(MUslbstrat[0,:])])

        MUs[:,:]=MUslbstrat[:,:]
        factionacronymslbstrat=['BM','BR','CD','DE','DC','DW','EM','GC','GS','HE','KH','KS','LM','NG','NR','OK','SK','SL','TK','TZ','VC','VP','WE','WC']

        factionacronyms=['']*len(factionacronymslbstrat)


        factionacronyms[:]=factionacronymslbstrat[:]

         
    else:
        Matrixfile=f"{flags.usematrix}"+".csv"
        facnamesopen=f"{flags.usematrix}"+".txt"

        if Path(Matrixfile).is_file()==False or Path(facnamesopen).is_file()==False:
            await ctx.send(f"Could not find desired files please try reuploading them")
        
            return 
        if Matrixfile==MUmatrixfilenamestrat and cleareduse==False:
            await ctx.send(f"You cannot access this file.")
        
            return            
        df = pd.read_csv(Matrixfile)
        MUs=pd.DataFrame(df).to_numpy()
        facfile=open(facnamesopen,'r')
        faclines=facfile.readlines()
        facfile.close()
        commacountfac=0
        for i in range(len(faclines[0])):
            if faclines[0][i]==',':
                commacountfac=1+commacountfac
        factionacronyms=['']*(commacountfac+1)
        k=0
        for i in range(len(faclines[0])):
            if faclines[0][i]==',':
                k=k+1
            else: 
                factionacronyms[k]=factionacronyms[k]+faclines[0][i]
                              
    MUtemp=np.zeros([len(MUs[:,0]),len(MUs[0,:])])
    MUtemp[:,:]=MUs[:,:]
    MUcount=len(factionacronyms)
    counter=0
    for i in range(MUcount-2):
        for j in range(i+1,MUcount-1):
            for k in range(j+1,MUcount):
                counter=counter+1             
    [unplay,errorflagnow]=parse(flags.unplayablefactions,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.unplayablefactions}")
    	return
    [oppunplay,errorflagnow]=parse(flags.opponentunplayablefactions,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.opponentunplayablefactions}")    
    	return
    [globalsb,errorflagnow]=parse(flags.globalbans,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.globalbans}") 
    	return   
    [avoidfacs,errorflagnow]=parse(flags.avoid,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.avoid}")  
    	return  
    [includefacs,errorflagnow]=parse(flags.mustinclude,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.mustinclude}")    
    	return 
    [unban,errorflagnow]=parse(flags.unbannable,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.unbannable}")    
    	return
    [oppunban,errorflagnow]=parse(flags.opponentunbannable,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.opponentunbannable}")    
    	return    	
    	     	
    preban=oppunplay+globalsb
    allunplayable=unplay+globalsb

    if len(preban)>=1:
        prebanindex= [0] * (len(preban))
        
        for m in range(len(preban)):
            for n in range(len(factionacronyms)):
                if preban[m]==factionacronyms[n]:
                    prebanindex[m]=n    
        for m in range(len(preban)):
            MUtemp[:,int(prebanindex[m])]=10
    
    if len(allunplayable)>=1:
        allunplayableindex= [0] * (len(allunplayable))
        
        for m in range(len(allunplayable)):
            for n in range(len(factionacronyms)):
                if allunplayable[m]==factionacronyms[n]:
                    allunplayableindex[m]=n    
        for m in range(len(allunplayable)):
            MUtemp[int(allunplayableindex[m]),:]=-10
            
    if len(includefacs)>=1:
        includefacsindex= [0] * (len(includefacs))
        
        for m in range(len(includefacs)):
            for n in range(len(factionacronyms)):
                if includefacs[m]==factionacronyms[n]:
                    includefacsindex[m]=n     

    
    if len(avoidfacs)>=1:
        avoidfacsindex= [0] * (len(avoidfacs))
        
        for m in range(len(avoidfacs)):
            for n in range(len(factionacronyms)):
                if avoidfacs[m]==factionacronyms[n]:
                    avoidfacsindex[m]=n            
            
    if len(oppunban)>=1:
        oppunbanindex= [0] * (len(oppunban))
        
        for m in range(len(oppunban)):
            for n in range(len(factionacronyms)):
                if oppunban[m]==factionacronyms[n]:
                    oppunbanindex[m]=n
    if len(unban)>=1:
        unbanindex= [0] * (len(unban))
        
        for m in range(len(unban)):
            for n in range(len(factionacronyms)):
                if unban[m]==factionacronyms[n]:
                    unbanindex[m]=n     
                                   
    MUcount=len(factionacronyms)

    picksnow=np.zeros([2,MUcount])
    MUchoices=np.zeros([MUcount])
    MUchoicesindex=np.zeros([MUcount,2])    
    uselength=np.zeros([9,])
    faclength=np.zeros([counter,9,])
    yourfaction=np.zeros([counter,9,2*MUcount,])
    enemyfaction=np.zeros([counter,9,2*MUcount,])

    MUindexes=np.zeros([counter,9,2])
    invalidmus=0
    banlist=np.zeros([counter,9,2,bans,])
    sidednesslist=[-4 ,-3, -2, -1, 0,1,2,3,4]

    for i in range(MUcount-1):
            for j in range(i+1,MUcount):
                    picksnow[0,:]=MUtemp[i,:]
                    picksnow[1,:]=MUtemp[j,:]
                    indexnow=[i,j]
                    for l in range(MUcount):
                    	MUchoicesindex[l,:]=np.argsort(picksnow[:,l])
                    	MUchoices[l]=picksnow[int(MUchoicesindex[l,1]),l]
      

                    Expectworstindex = np.argsort(MUchoices)

                    Expectworstvalue=MUchoices[Expectworstindex[bans]]   
                    
                    if len(oppunban)>0:
                    	oppforcedtrue=0
                    	for n in range(len(oppunbanindex)):
                    		if forcedMUsopp[n,0]==1 and forcedMUsopp[n,3]==Expectworstvalue:
                    			oppforcedtrue=1
                    			
                    	
                    		                       
                    
                    #Determines what the ban is and if it is flexible 
                    banflex=np.zeros([bans,])
                    banindex=np.zeros([bans,])
                    banshift=np.zeros([bans,])
                    for q in range(bans):
                    	banindex[q]=Expectworstindex[q]
                    	banshift[q]=q
                    	if MUchoices[int(banindex[q])]==Expectworstvalue:
                    		banflex[q]=1
                    
                    
                    forceoverall=0
                    if len(unban)>0:
                    	noneencountered=False
                    	forcedata=np.zeros([len(unbanindex),3,])
                    	forceoverall=0
                    	nonenecountered=True
                    	forcedata[:,1]=np.ones([len(unbanindex),])*Expectworstvalue
                    	for q in range(bans):
                    		for n in range(len(unbanindex)):
                    			for qq in range(bans):
                    				if banindex[q]==banindex[qq] and qq!=q:
                    					noneencountered=False
                    					if q>qq:
                    						banshift[q]=banshift[q]+1
                    						banindex[q]=Expectworstindex[int(banshift[q])]
                    					else: 
                    						banshift[qq]=banshift[qq]+1
                    						banindex[qq]=Expectworstindex[int(banshift[qq])]
                    			if banindex[q]==unbanindex[n]:
	                   				noneencountered=False
	                   				banshift[q]=banshift[q]+1
	                   				banindex[q]=Expectworstindex[int(banshift[q])]				        				
	                   				if Expectworstvalue > MUchoices[int(unbanindex[n])]:
	                   					Expectworstvalue = MUchoices[int(unbanindex[n])]
	                   					forceoverall=1
	                   					forcedata[n,0]=1
	                   					forcedata[n,1]=MUchoices[unbanindex[n]]
	                   					forcedata[n,2]=unbanindex[n]


                    			
                    	if np.min(forcedata[:,1])<Expectworstvalue:
                    	    		Expectworstvalue=np.min(forcedata[:,1])
#does this do anything?			    	

                    	for q in range(bans):
                    		if MUchoices[int(banindex[q])]>=Expectworstvalue:
                    			banflex[q]=1			    	
			  

		     	     
		
		    #if any factions are to be avoided this section ensures they are avoided
                    if len(avoidfacs)>=1:
                        encounters=np.zeros([len(avoidfacsindex),])
                        for n in range(len(avoidfacsindex)):                     
                        		if MUchoices[avoidfacsindex[n]]==Expectworstvalue:                                     
                                              encounters[n]=1
                                              if len(unban)>0:
                                              	for m in range(len(unbanindex)):
                                              		if avoidfacsindex[n]==unbanindex[m]:
                                              			Expectworstvalue=-10
                                              
                        if sum(encounters)>sum(banflex):
                        	Expectworstvalue=-10
                        elif sum(encounters)>0:
                        	for n in range(len(avoidfacsindex)):
                        		for q in range(bans):                        		
                        			if encounters[n]==1 and banflex[q]==1:
                        				banflex[q]=0
                        				banindex[q]=avoidfacsindex[n]
					
				 
			 	
                    
                    #if mustinclude is active this ensures that the included factions are present                                                          
                    
                    if len(includefacs)>=1:
                    	included=0
                   
                    	for n in range(len(includefacsindex)):
                    		if includefacsindex[n]==i or includefacsindex[n]==j:
                    			included=included+1
                    
                    	if included!=len(includefacsindex):
                    		Expectworstvalue=-10
                    		
                    #sorts out any MUs that contain an invalid faction		
                    for p in range(2):
                    	if np.sum(picksnow[p,:])==-10*len(picksnow[p,:]):
                    		Expectworstvalue=-10	
                    	
		    
                    
                    indexnow=[i,j]
                    for g in range(9):
                        if Expectworstvalue<-4:
                            invalidmus=invalidmus+1
                        if float(Expectworstvalue)==float(sidednesslist[g]):
                        
                            for l in range(MUcount):
                                if float(MUchoices[l])==float(sidednesslist[g]):
                                    for w in range(2):
                                        if float(picksnow[w,l])==float(sidednesslist[g]):                                          
                                            yourfaction[int(uselength[g]),g,int(faclength[int(uselength[g]),g])]=indexnow[w]
                                            enemyfaction[int(uselength[g]),g,int(faclength[int(uselength[g]),g])]=l
                                            faclength[int(uselength[g]),g]=faclength[int(uselength[g]),g]+1
                                            
                            MUindexes[int(uselength[g]),g,:]=[i,j]
                            banlist[int(uselength[g]),g,0,:]=banindex
                            banlist[int(uselength[g]),g,1,:]=banflex
                            if len(unban)>0 and forceoverall==1:
                            	yourfaction[int(uselength[g]),g,:]=np.zeros([2*MUcount,])
                            	enemyfaction[int(uselength[g]),g,:]=np.zeros([2*MUcount,])
                            	faclength[int(uselength[g]),g]=0
                            	for n in range(len(unbanindex)):
                            		if float(MUchoices[unbanindex[n]])==float(sidednesslist[g]):
                            			for w in range(3):
                            				if float(picksnow[w,unbanindex[n]])==float(sidednesslist[g]):
                            					yourfaction[int(uselength[g]),g,int(faclength[int(uselength[g]),g])]=indexnow[w]
                            					enemyfaction[int(uselength[g]),g,int(faclength[int(uselength[g]),g])]=n
                            					faclength[int(uselength[g]),g]=faclength[int(uselength[g]),g]+1
                                                    
                            uselength[g]=uselength[g]+1


    trigger=0                    
    for h in range(len(uselength)):
        r=len(uselength)-h-1
        if uselength[r]>0 and trigger<1:
            trigger=1
            for y in range(int(uselength[r])):
                orderlist=np.argsort(faclength[0:int(uselength[r]),r],0)
                if y>=printlimit:
                	await ctx.send(f"There were a total of {int(uselength[r])} total possible picks.  Printing stopped at the first {printlimit}."+ " To print more use the option printlimit: N to print N possible picks." )
                	break


                ynew=orderlist[y]
                fullsend=""
                fullsend=fullsend+f'Best MUs eveness: '+str(sidednesslist[r])+'\n'
                if bans>0:
                	fullsend=fullsend+f"Pick: {factionacronyms[int(MUindexes[ynew,r,0])]}, {factionacronyms[int(MUindexes[ynew,r,1])]} Ban: "
                	for h in range(bans):
                		if banlist[ynew,r,1,h]==0:
                		    fullsend=fullsend+f" {factionacronyms[int(banlist[ynew,r,0,h])]},"
                		else:
                		    fullsend=fullsend+f"Any"
                	fullsend=fullsend+f"\n"
                                        	                	
                	
                if bans==0:
                	fullsend=fullsend+f"Pick: {factionacronyms[int(MUindexes[ynew,r,0])]}, {factionacronyms[int(MUindexes[ynew,r,1])]} \n"
                fullsend=fullsend+f"Expected MUs are: \n"
                for x in range(int(faclength[ynew,r])):
                	fullsend=fullsend+f"{factionacronyms[int(yourfaction[ynew,r,x])]} vs {factionacronyms[int(enemyfaction[ynew,r,x])]}, "
                await ctx.send(fullsend)

    await ctx.send(f"End Results")
    return   


   

class CounterPick2Flags(commands.FlagConverter):
        usematrix: str=''
        unplayablefactions: list=[]
        opponentunplayablefactions: list=[]
        globalbans: list = []
        bannumber: list=[0]
        mustinclude: list=[]
        avoid: list=[]
        printlimit: int=15
        banned: list=[]
        picked: list=[]
        unbannable: list=[]
        opponentunbannable: list=[]  
        
        
@bot.command()
async def counterpick2(ctx,*,flags: CounterPick2Flags):
	
    if ctx.guild:
        await ctx.channel.send('This is not a DM, please DM the bot so it does not spam')
        return
    bans=int(flags.bannumber[0])
    printlimit=int(flags.printlimit)
    global MUslb
    global MUslbstrat


    cleareduse=False
    guild = bot.get_guild(guild1_id)
    try:
          member = await guild.fetch_member(ctx.author.id)


          for r in member.roles:
            for rolentry in roleids:
              if r.id == rolentry:
                 cleareduse=True
    except:
          cleareduse=False

    if flags.usematrix=='' and cleareduse==False:
        MUs=np.zeros([len(MUslb[:,0]),len(MUslb[0,:])])

        MUs[:,:]=MUslb[:,:]
        factionacronymslb=['VP','VC','TK','WC','NR','BM','GS','SK','LM','DE','HE','WE','DW','EM','BR','KH','NG','SL','TZ','GC','KS','OK','CD']
        factionacronyms=['']*len(factionacronymslb)

        factionacronyms[:]=factionacronymslb[:]

    elif flags.usematrix=='' and cleareduse==True:
        MUs=np.zeros([len(MUslbstrat[:,0]),len(MUslbstrat[0,:])])

        MUs[:,:]=MUslbstrat[:,:]
        factionacronymslbstrat=['BM','BR','CD','DE','DC','DW','EM','GC','GS','HE','KH','KS','LM','NG','NR','OK','SK','SL','TK','TZ','VC','VP','WE','WC']
        factionacronyms=['']*len(factionacronymslbstrat)

        factionacronyms[:]=factionacronymslbstrat[:]

         
    else:
        Matrixfile=f"{flags.usematrix}"+".csv"
        facnamesopen=f"{flags.usematrix}"+".txt"

        if Path(Matrixfile).is_file()==False or Path(facnamesopen).is_file()==False:
            await ctx.send(f"Could not find desired files please try reuploading them")
        
            return 
        if Matrixfile==MUmatrixfilenamestrat and cleareduse==False:
            await ctx.send(f"You cannot access this file.")
        
            return            
        df = pd.read_csv(Matrixfile)
        MUs=pd.DataFrame(df).to_numpy()
        facfile=open(facnamesopen,'r')
        faclines=facfile.readlines()
        facfile.close()
        commacountfac=0
        for i in range(len(faclines[0])):
            if faclines[0][i]==',':
                commacountfac=1+commacountfac
        factionacronyms=['']*(commacountfac+1)
        k=0
        for i in range(len(faclines[0])):
            if faclines[0][i]==',':
                k=k+1
            else: 
                factionacronyms[k]=factionacronyms[k]+faclines[0][i]
                        
    MUtemp=np.zeros([len(MUs[:,0]),len(MUs[0,:])])
    MUtemp[:,:]=-1*np.transpose(MUs[:,:])
    MUcount=len(factionacronyms)
    counter=0
    for i in range(MUcount-2):
        for j in range(i+1,MUcount-1):
            for k in range(j+1,MUcount):
                counter=counter+1             
    [ oppunplay,errorflagnow]=parse(flags.unplayablefactions,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.unplayablefactions}")
    	return
    [picked,errorflagnow]=parse(flags.picked,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.picked}")
    	return
    [banned,errorflagnow]=parse(flags.banned,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.banned}")
    	return
    [unplay,errorflagnow]=parse(flags.opponentunplayablefactions,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.opponentunplayablefactions}")    
    	return
    [globalsb,errorflagnow]=parse(flags.globalbans,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.globalbans}") 
    	return   
    [avoidfacs,errorflagnow]=parse(flags.avoid,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.avoid}")  
    	return  
    [includefacs,errorflagnow]=parse(flags.mustinclude,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.mustinclude}")    
    	return 
    [ oppunban,errorflagnow]=parse(flags.unbannable,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.unbannable}")    
    	return
    [ unban,errorflagnow]=parse(flags.opponentunbannable,factionacronyms)
    if errorflagnow==1:
    	await ctx.send(f"WARNING AN ERROR PARSING THE INPUT: {flags.opponentunbannable}")    
    	return    	
    	     	
    preban=oppunplay+globalsb+banned
    allunplayable=unplay+globalsb

    if len(preban)>=1:
        prebanindex= [0] * (len(preban))
        
        for m in range(len(preban)):
            for n in range(len(factionacronyms)):
                if preban[m]==factionacronyms[n]:
                    prebanindex[m]=n    
        for m in range(len(preban)):
            MUtemp[:,int(prebanindex[m])]=10
    
    if len(allunplayable)>=1:
        allunplayableindex= [0] * (len(allunplayable))
        
        for m in range(len(allunplayable)):
            for n in range(len(factionacronyms)):
                if allunplayable[m]==factionacronyms[n]:
                    allunplayableindex[m]=n    
        for m in range(len(allunplayable)):
            MUtemp[int(allunplayableindex[m]),:]=-10
            
    if len(includefacs)>=1:
        includefacsindex= [0] * (len(includefacs))
        
        for m in range(len(includefacs)):
            for n in range(len(factionacronyms)):
                if includefacs[m]==factionacronyms[n]:
                    includefacsindex[m]=n     

    
    if len(avoidfacs)>=1:
        avoidfacsindex= [0] * (len(avoidfacs))
        
        for m in range(len(avoidfacs)):
            for n in range(len(factionacronyms)):
                if avoidfacs[m]==factionacronyms[n]:
                    avoidfacsindex[m]=n            
            
    if len(oppunban)>=1:
        oppunbanindex= [0] * (len(oppunban))
        
        for m in range(len(oppunban)):
            for n in range(len(factionacronyms)):
                if oppunban[m]==factionacronyms[n]:
                    oppunbanindex[m]=n
    if len(unban)>=1:
        unbanindex= [0] * (len(unban))
        
        for m in range(len(unban)):
            for n in range(len(factionacronyms)):
                if unban[m]==factionacronyms[n]:
                    unbanindex[m]=n     
    pickedindex= [0] * (len(picked))
    
    for m in range(len(picked)):
        for n in range(len(factionacronyms)):
            if picked[m]==factionacronyms[n]:
                pickedindex[m]=n
    if len(pickedindex)!=2:
    	await ctx.send(f"Error, the command did not recognize 2 factions as the input from {picked}.") 
    	return
        
    if len(banned)>=1:
        bannedindex= [0] * (len(banned))
        
        for m in range(len(banned)):
            for n in range(len(factionacronyms)):
                if banned[m]==factionacronyms[n]:
                    bannedindex[m]=n                                   
    MUcount=len(factionacronyms)

    picksnow=np.zeros([2,MUcount])
    MUchoices=np.zeros([MUcount])
 #   oppban=np.zeros([MUcount])
    MUchoicesindex=np.zeros([MUcount,2])    


    MUindexes=np.zeros([counter,9,2])
    invalidmus=0
    banlist=np.zeros([counter,9,2,bans,])
    sidednesslist=[-4 ,-3, -2, -1, 0,1,2,3,4]
    
    
    picksnow[0,:]=MUtemp[pickedindex[0],:]
    picksnow[1,:]=MUtemp[pickedindex[1],:]
    indexnow=pickedindex
    for l in range(MUcount):
    	MUchoicesindex[l,:]=np.argsort(picksnow[:,l])
    	MUchoices[l]=picksnow[int(MUchoicesindex[l,1]),l]
   # 	oppban[l]=indexnow[int(MUchoicesindex[l,2])]
 #   oppbanflexnow=np.zeros([MUcount,])    


    Expectworstindex = np.argsort(MUchoices)

    Expectworstvalue=MUchoices[Expectworstindex[bans]]   
        
    
    #Determines what the ban is and if it is flexible 
    banflex=np.zeros([bans,])
    banindex=np.zeros([bans,])
    banshift=np.zeros([bans,])
    for q in range(bans):
    	banindex[q]=Expectworstindex[q]
    	banshift[q]=q
    	if MUchoices[int(banindex[q])]==Expectworstvalue:
    		banflex[q]=1
    
    
    forceoverall=0

		     	     
		
		    #if any factions are to be avoided this section ensures they are avoided
    if len(avoidfacs)>=1:
        encounters=np.zeros([len(avoidfacsindex),])
        for n in range(len(avoidfacsindex)):                     
        		if MUchoices[avoidfacsindex[n]]==Expectworstvalue:                                     
                              encounters[n]=1
                              if len(unban)>0:
                              	for m in range(len(unbanindex)):
                              		if avoidfacsindex[n]==unbanindex[m]:
                              			Expectworstvalue=-10
                              
        if sum(encounters)>sum(banflex):
        	Expectworstvalue=-10
        elif sum(encounters)>0:
        	for n in range(len(avoidfacsindex)):
        		for q in range(bans):                        		
        			if encounters[n]==1 and banflex[q]==1:
        				banflex[q]=0
        				banindex[q]=avoidfacsindex[n]
					
				 
			 	
    
    #if mustinclude is active this ensures that the included factions are present                                                          
    
    if len(includefacs)>=1:
    	included=0
   
    	for n in range(len(includefacsindex)):
    		if includefacsindex[n]==i or includefacsindex[n]==j or includefacsindex[n]==k:
    			included=included+1
    
    	if included!=len(includefacsindex):
    		Expectworstvalue=-10
    		
    #sorts out any MUs that contain an invalid faction		
    for p in range(2):
    	if np.sum(picksnow[p,:])==-10*len(picksnow[p,:]):
    		Expectworstvalue=-10	
    	
		    
    uselength=np.zeros([MUcount,])
    faclength=np.zeros([MUcount,])
    faclength=np.zeros([MUcount,])

    yourfaction=np.zeros([MUcount,3,])
    enemyfaction=np.zeros([MUcount,])    
    banfaction=np.zeros([MUcount,])    
  #  oppbanflex=np.zeros([MUcount,])    
#    for l in range(MUcount):
   #   if picksnow[int(MUchoicesindex[l,2]),l]==picksnow[int(MUchoicesindex[l,1]),l]:
 #         oppbanflexnow[l]=1
        
    countfactions=0
    for l in range(MUcount):
        if float(MUchoices[l])==float(Expectworstvalue):
            for w in range(2):
                if float(picksnow[w,l])==float(Expectworstvalue):                                          
                    yourfaction[countfactions,int(faclength[countfactions])]=indexnow[w]
                    enemyfaction[countfactions]=l
                    faclength[countfactions]=faclength[countfactions]+1
        #            banfaction[countfactions]=oppban[l]
      #              oppbanflex[countfactions]=oppbanflexnow[l]
            countfactions=countfactions+1
                    
                    


    for y in range(int(countfactions)):
        orderlist=np.argsort(faclength[0:countfactions],0)
        if y>=printlimit:
        	await ctx.send(f"There were a total of {int(countfactions)} total possible picks.  Printing stopped at the first {printlimit}."+ " To print more use the option printlimit: N to print N possible picks." )
        	break
    
    
        ynew=orderlist[y]
        fullsend=""
        fullsend=fullsend+f'Best MUs eveness: '+str(-1*Expectworstvalue)+'\n'

                                	                	
        	
        fullsend=fullsend+f"Pick: {factionacronyms[int( enemyfaction[ynew])]}\n"
   #     if oppbanflex[ynew]==1:
    #        fullsend=fullsend+f"Ban: Any\n"
     #   else:
      #      fullsend=fullsend+f"Ban: {factionacronyms[int(banfaction[ynew])]}\n"
        fullsend=fullsend+f"Expected MUs are: \n"
        for x in range(int(faclength[ynew])):
        	fullsend=fullsend+f"{factionacronyms[int( enemyfaction[ynew])]} vs {factionacronyms[int( yourfaction[ynew,x])]}, "
        await ctx.send(fullsend)

    await ctx.send(f"End Results")
    return   





if __name__ == "__main__":
    bot.run(BOT_TOKEN)