#GOMTVNET - by Futurefive 2011
#Content scraped from m.gomtv.net
#Thanks to Voinage for his XBMC plugin tutorial and boilerplate code http://wiki.xbmc.org/index.php?title=HOW-TO_write_plugins_for_XBMC
#Thanks to Temhil for his XBMC Eclipse debugging tutorial http://wiki.xbmc.org/index.php?title=HOW-TO_debug_Python_Scripts_with_Eclipse#Add_Pydev_Python_source_code_.28pysrc.29_to_XBMC

from BeautifulSoup import BeautifulSoup
import urllib2, urllib
import sys, os
import re
import simplejson as json
import xbmc, xbmcgui, xbmcplugin
import cookielib

BASE_COOKIE_PATH = os.path.join(xbmc.translatePath( "special://profile/" ), "addon_data", os.path.basename(os.getcwd()), 'cookie.txt')

# plugin modes
MODE_MATCHLIST = 1
MODE_VODLINKS = 2

USER_AGENT = 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:5.0) Gecko/20100101 Firefox/5.0'

#Prevent page load from potentially running infinitely
MAX_PAGE_LOADS = 20
 
# plugin handle
handle = int(sys.argv[1])

# build opener with HTTPCookieProcessor
cookie_jar = cookielib.LWPCookieJar(BASE_COOKIE_PATH)
# load cookie if it exists
if not os.path.exists(os.path.dirname(BASE_COOKIE_PATH)):
    os.makedirs(os.path.dirname(BASE_COOKIE_PATH))
if (os.path.isfile(BASE_COOKIE_PATH)):
    cookie_jar.load(BASE_COOKIE_PATH)

opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookie_jar))

opener.addheaders = [('User-agent',  USER_AGENT)]
urllib2.install_opener(opener)


##########################
##       LEAGUES
##########################

def show_leagues():
    url = 'http://m.gomtv.net/league/'
    
    f = opener.open( url )
    html = f.read()
    f.close()
    cookie_jar.save()

    soup = BeautifulSoup(html)
    ul_list = soup('ul', {'class':'list_wrap'})

    for i in ul_list:
        league_name = i('li', {'class':'namelist_long'})[0](text=True)[0]
        league_url = i('li', {'class':'nextbtn'})[0].a['href'].split('=')
        league_id = league_url[len(league_url)-1]
        league_ajax_url = "http://m.gomtv.net/ajax/getVideoList.gom?league="+league_id+"&pid=&mid=&page="
        addDirectoryItem(league_name.strip(), True, {'mode':'1', 'name':league_name, 'url':league_ajax_url})

    xbmcplugin.endOfDirectory(handle=handle, succeeded=True)


##########################
##      MATCHLIST
##########################
#http://m.gomtv.net/ajax/getVideoList.gom?league=22824&pid=&mid=&page=1
#Above AJAX returns 10 items per page, need to make multiple request to show more items
#Works with both GET or POST
def show_matches(base_url, load_all = False):
    pages_loaded = 0
    empty_page = False #have we hit an empty response
    updateListing = True
    
    if load_all == False:
        updateListing = False
        
    while pages_loaded < MAX_PAGE_LOADS:
        url = base_url+str(pages_loaded+1)
        
        print "Opening: "+url
        
        f = opener.open( url )
        html = f.read()
        f.close()
        cookie_jar.save()
        
        #If html is empty then break the loop
        if not html:
            print "Empty HTML response...breaking loop "+str(pages_loaded)
            empty_page = True
            break
        
        soup = BeautifulSoup(html)
        li_list = soup('li', {'class':'playlist'})
    
        for i in li_list:
            vod_url    = re.compile("location.href='(.+?)';").findall(i.dl['onclick'])[0] 
            thumb_href = i('dt', {'class':'thumbnail'})[0].span.img['src']
            date       = i('dd', {'class':'playdate'})[0](text=True)[0]
            match      = i('dd', {'class':'playmatch'})[0](text=True)[0]
            players    = i('dd')[len(i('dd'))-1](text=True) #gets last dd the class of the player container is inconsistent
            title = match+" - "+players[0]+" vs "+players[1]
            addDirectoryItem(title, True, {'mode':'2', 'name':title, 'url':vod_url}, MAX_PAGE_LOADS*10)
        
        pages_loaded = pages_loaded + 1
        
        if load_all is False and pages_loaded >= (perpage/10):
            print "Hit max page load value...breaking loop "+str(pages_loaded)
            break
    
    if load_all == False:
        addDirectoryItem('Load All Matches...', True, {'mode':'1', 'name':'Load All Matches...', 'url':base_url, 'load_all':'True'}, 1)
    
    xbmcplugin.endOfDirectory(handle=handle, succeeded=True, updateListing=updateListing)


##########################
##       VODLINKS
##########################
def show_match_vod_links(url, name):
    f = opener.open( url )
    html = f.read()
    f.close()
    cookie_jar.save()

    soup = BeautifulSoup(html)

    league_id = soup('input', {'id':"leagueidByHtml"})[0]['value']
    
    print "League_id: "+league_id
    
    cur_game = None
    new_item_exists = True
    item_num = 0
    
    while new_item_exists is not False:
        try:
            cur_game = soup('li', {'class':'play_pybtn'})[item_num].a['href']
        except IndexError:
            #there are no more items so break the loop
            new_item_exists = False
            continue
        #if no error then parse the game info and add to the game_list 
        game_info = parse_game(cur_game)       
        mp4_url = load_mp4_url(game_info, league_id)
        
        if mp4_url is False:
            print "Error loading MP4 Steam Gox. Most likely the user has no premium ticket for this VOD"
            notify('small', 'Could not detect every stream', 'Make sure you are logged in and have a premium ticket for this season')
            break
        
        mp4_url = mp4_url+'|User-agent='+urllib.quote(USER_AGENT)+'&Referer='+urllib.quote('http://m.gomtv.net/')  
        mp4_url = mp4_url.replace(' ', '%20')
        
        print mp4_url
        
        addLinkItem(game_info['title']+", Set "+game_info['setnum'], mp4_url)
        
        item_num = item_num + 1
    
    xbmcplugin.endOfDirectory(handle=handle, succeeded=True)
        

def parse_game (game_href):
    game_info = re.compile('javascript:getVideoUrl\((.+?)\);').findall(game_href)[0]
    game_info = game_info.replace("'", '"') #the javascript uses '' to enclose variables but it needs to be "" to be successfully parsed by json.loads
    game_info = json.loads(game_info)
    return game_info

#to do this we need to load the what gom calls the gox file which contains a link to the stream
def load_mp4_url (game_info, league_id):
    gox_url = 'http://m.gomtv.net/ajax/getGox.gom?conid='+game_info['conid']+'&leagueid='+league_id+'&title='+urllib.quote(game_info['title'])+'&target=vod&strLevel='+game_info['level']+'&setnum='+game_info['setnum']+'&vjoinid='+game_info['vjoinid']
    print "Gox: "+gox_url
    f = opener.open( gox_url )
    data = f.read()
    f.close()
    
    error_code = re.compile('<errCode>(.+?)</errCode>').findall(data)[0]
    
    if error_code == '0':
        #pull out the stream link from the response
        return re.compile('<goxUrl><!\[CDATA\[(.+?)\]\]></goxUrl>').findall(data)[0]
    else:
        return False

################
##   LOGIN
################
# There should be a check to see if you are already logged in first
# So it should save the cookie to file on first load then attempt to load page using stored cookie, if the page load fails then it should attempt login and store new cookie

def gomtv_login():
    if email == '' or password == '':
        notify('small', 'Login Failed', 'Please Enter Your Email and Password in the Addon Settings')
    
    p = urllib.urlencode( { 'mb_username':email, 'mb_password':password, 'cmd':'login', 'rememberme':'1'} )

    # perform login with params
    f = opener.open( 'http://m.gomtv.net/process/loginProcess.gom', p)
    login_status = f.read()
    f.close()
    cookie_jar.save()
    
    # Response of 1 means success anything else is a failure response
    print "Login Response: "+login_status
    
    if login_status == '1':
        notify('small', 'Login Success', 'You are now logged into GomTV.net')
    else:
        notify('small', 'Login Failed', 'Please check your email and password. Error Code: '+login_status)


# utility functions
def parameters_string_to_dict(parameters):
    ''' Convert parameters encoded in a URL to a dict. '''
    paramDict = {}
    if parameters:
        paramPairs = parameters[1:].split("&")
        for paramsPair in paramPairs:
            paramSplits = paramsPair.split('=')
            if (len(paramSplits)) == 2:
                paramDict[paramSplits[0]] = paramSplits[1]
    return paramDict
 
def addDirectoryItem(name, isFolder=True, parameters={}, totalItems=1):
    ''' Add a list item to the XBMC UI.'''
    li = xbmcgui.ListItem(name)
    dir_url = sys.argv[0] + '?' + urllib.urlencode(parameters)
    return xbmcplugin.addDirectoryItem(handle=handle, url=dir_url, listitem=li, isFolder=isFolder, totalItems=totalItems)

def addLinkItem(name, url, iconimage = ""):
    #liz=xbmcgui.ListItem(name, iconImage="DefaultVideo.png", thumbnailImage=iconimage)
    liz=xbmcgui.ListItem(name, iconImage="DefaultVideo.png")
    liz.setInfo( type="Video", infoLabels={ "Title": name } )
    liz.setProperty('IsPlayable', 'true')
    #liz.setProperty('mimetype', 'video/mp4')
    return xbmcplugin.addDirectoryItem(handle=handle, url=url, listitem=liz)

def notify(typeq,title,message,times=''):
     #simplified way to call notifications. common notifications here.
     if title == '':
          title='GomTvNet Notification'
     if typeq == 'small':
          if times == '':
               times='6000'
          #smallicon=xbmcpath(art,'smalltransparent2.png')
          xbmc.executebuiltin("XBMC.Notification("+title+","+message+","+times+")")
     if typeq == 'big':
          dialog = xbmcgui.Dialog()
          dialog.ok(' '+title+' ', ' '+message+' ')
          

##########################
##        MAIN
##########################     

print "#################### GOMTVNET PLUGIN START ######################"

pluginhandle = int(sys.argv[1])
email    = xbmcplugin.getSetting(pluginhandle, "email")
password = xbmcplugin.getSetting(pluginhandle, "password")
perpage  = ( 10, 20, 30, 40, 50, )[int(xbmcplugin.getSetting(pluginhandle, "perpage"))]

params = parameters_string_to_dict(sys.argv[2])
mode = int(params.get("mode", "0"))
url = None
name = None
load_all = None #only used in MODE_MATCHLIST

try:
    url = urllib.unquote_plus(params.get("url", ""))
    name = urllib.unquote_plus(params.get("name", ""))
    load_all = ('True' == params.get("load_all", "False"))
except:
    print "Error parsing params"
    pass


#print "sys.argv[2] - "+str(sys.argv[2])
#print "Params: "+str(params)
print("Mode: %s" % mode)
print "URL: "+str(url)
print "Name: "+str(name)
print "load_all: "+str(load_all)
print "Perpage: "+str(perpage)


##### DETERMINE PAGE TO LOAD #####
if not sys.argv[2]:
    print "show_leagues"
    show_leagues()
    gomtv_login()
       
elif mode==MODE_MATCHLIST:
    print "show_matches"
    show_matches(url, load_all)
        
elif mode==MODE_VODLINKS:
    print "show_match_vod_links"
    #gomtv_login()
    show_match_vod_links(url, name)

print "###################### GOMTVNET PLUGIN END ########################"