from youtubesearchpython import VideosSearch, Video, ResultMode
import re

'''
  return is string is url
'''
def isUrl(url):
  url_expression = r'/[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*)?/gi'

  is_url = re.match(url_expression, url)

  return is_url

'''
    get URL of the specific song from youtube 
    return title and URL of the song 
'''
def getUrl(query):
    if isUrl(query):
      top_result = Video.get('https://www.youtube.com/watch?v=z0GKGpObgPY', mode = ResultMode.json)
    else:
      search = VideosSearch(query, limit = 1)
      top_result = search.result()['result'][0]

    title = top_result['title']
    link = top_result['link']

    return title, link