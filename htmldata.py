"""
Manipulate HTML or XHTML documents.

Version 1.0.2.  This source code has been placed in the
public domain by Connelly Barnes.

Features:

 - Translate HTML back and forth to data structures.
   This allows you to read and write HTML documents
   programmably, with much flexibility.
 - Extract and modify URLs in an HTML document.

"""

# -------------------------------------------------------------------
# Globals
# -------------------------------------------------------------------

import re
import shlex
import string
import urllib
import urlparse

# Translate text between these strings as plain text (not HTML).
_IGNORE_TAGS = [('script', '/script'),
               ('style',  '/style')]

_BEGIN_COMMENT = '<!--'
_END_COMMENT   = '-->'

# -------------------------------------------------------------------
# HTML <-> Data structure
# -------------------------------------------------------------------

def tagextract(doc):
  """
  Convert HTML to data structure.

  Returns a list.  HTML tags become (name, keyword_dict) tuples
  within the list, while plain text becomes strings within the
  list.  All tag names are lowercased and stripped of whitespace.
  Tags which end with forward slashes have a single forward slash
  placed at the end of their name, to indicate that they are XML
  unclosed tags.

  Example:

  >>> tagextract('<img src=hi.gif alt="hi">foo<br><br/></body>')
  [('img', {'src': 'hi.gif', 'alt': 'hi'}), 'foo',
   ('br', {}), ('br/', {}), ('/body', {})]

  Text between '<script>' and '<style>' is rendered directly to plain
  text. This prevents rogue '<' or '>' characters from interfering
  with parsing.

  >>> tagextract('<script type="a"><blah>var x; </script>')
  [('script', {'type': 'a'}), '<blah>var x; ', ('/script', {})]

  Text inside the comment strings '<!--' and '-->' is also rendered
  as plain text.  Opening and closing comments are translated into
  ('!--', {}) and ('--', {}), respectively.

  Example:

  >>> tagextract('<!-- blah -->')
  ['!--', ' blah ', '--']
  """
  L = _full_tag_extract(doc)
  for i in range(len(L)):
    if isinstance(L[i], _TextTag):
      # _TextTag object.
      L[i] = L[i].text
    else:
      # _HTMLTag object.
      L[i] = (L[i].name, L[i].attrs)
  return L

def tagjoin(L):
  """
  Convert data structure back to HTML.

  This reverses the tagextract() function.

  More precisely, if an HTML string is turned into a data structure,
  then back into HTML, the resulting string will be functionally
  equivalent to the original HTML.

  >>> tagjoin(tagextract(s))
  (string that is functionally equivalent to s)

  Three changes are made to the HTML by tagjoin(): tags are
  lowercased, key=value pairs are sorted, and values are placed in
  double-quotes.
  """
  ans = []
  for item in L:
    if isinstance(item, str):
      # Handle plain text.
      ans.append(item)
    elif item[0] == '--':
      # Handle closing comment.
      ans.append('-->')
    elif item[0] == '!--':
      # Handle opening comment.
      ans.append('<!--')
    else:
      # Handle regular HTML tag.
      (name, d) = item
      if name[-1:] == '/':
        rslash = ' /'
        name = name[:-1]
      else:
        rslash = ''
      tag_items = []
      items = d.items()
      items.sort()
      for (key, value) in items:
        if value != None:
          tag_items.append(key + '="' + value + '"')
        else:
          tag_items.append(key)
      tag_items = ' '.join(tag_items)
      if tag_items != '':
        tag_items = ' ' + tag_items
      ans.append('<' + name + tag_items + rslash + '>')
  return ''.join(ans)

def _ignore_tag_index(s, i):
  """
  Helper routine: Find index within _IGNORE_TAGS, or -1.

  If s[i:] begins with an opening tag from _IGNORE_TAGS, return the
  index.  Otherwise, return -1.
  """
  for (j, (a, b)) in enumerate(_IGNORE_TAGS):
    if s[i:i+len(a)+1].lower() == '<' + a:
      return j
  return -1

def _html_split(s):
  """
  Helper routine: Split string into a list of tags and non-tags.

  >>> html_split(' blah <tag text> more </tag stuff> ')
  [' blah ', '<tag text>', ' more ', '</tag stuff>', ' ']

  Tags begin with '<' and end with '>'.   Also, ''.join(L) == s.

  Special exceptions:

  '<script>', '<style>', and HTML comment tags ignore all HTML
  until the closing pair, and are added as three elements:

  >>> html_split(' blah<style><<<><></style><!-- hi -->' + \
                 ' <script language="Javascript"></>a</script>end')
  [' blah', '<style>', '<<<><>', '</style>', '<!--', ' hi ', '-->', \
   ' ', '<script language="Javascript">', '</>a', '</script>', 'end']

  """
  s_lower = s.lower()
  L = []

  i = 0               # Index of char being processed
  while i < len(s):
    c = s[i]
    if c == '<':
      # Left bracket, handle various cases.
      if s[i:i+len(_BEGIN_COMMENT)].startswith(_BEGIN_COMMENT):
        # HTML begin comment tag, '<!--'.  Scan for '-->'.
        L.append(_BEGIN_COMMENT)
        i += len(_BEGIN_COMMENT)
        i2 = s.find(_END_COMMENT, i)
        if i2 < 0:
          # No '-->'.  Append the rest as text.
          L.append(s[i:])
          break
        else:
          # Append the comment text.
          L.append(s[i:i2])
          # Then append the '-->' as a tag.
          L.append(s[i2:i2+len(_END_COMMENT)])
          i = i2 + len(_END_COMMENT)
      else:
        # Regular HTML tag.  Scan for '>'.
        orig_i = i
        i2 = s.find('>', i + 1)
        if i2 < 0:
          # No end '>'.  Append the rest as text.
          L.append(s[i:])
          break
        else:
          # Append the tag.
          L.append(s[i:i2+1])
          i = i2 + 1

        # Check whether we found a special ignore tag, eg '<script>'
        tagi = _ignore_tag_index(s, orig_i)
        if tagi >= 0:
          # It's an ignore tag.  Scan for the end tag.
          i2 = s_lower.find('<' + _IGNORE_TAGS[tagi][1], i)
          if i2 < 0:
            # No end tag.  Append the rest as text.
            L.append(s[i2:])
            break
          else:
            # Append the text sandwiched between the tags.
            L.append(s[i:i2])
            # Catch the closing tag with the next loop iteration.
            i = i2
    else:
      # Not a left bracket, append text up to next left bracket.
      i2 = s.find('<', i)
      if i2 < 0:
        # No left brackets, append the rest as text.
        L.append(s[i:])
        break
      else:
        L.append(s[i:i2])
      i = i2

  return L

def _shlex_split(s):
  """
  Like shlex.split(), but reversible, and for HTML.

  Splits a string into a list 'L' of strings.  List elements
  contain either an HTML tag name=value pair, an HTML name
  singleton (eg 'checked'), or whitespace.  ''.join(L) == s.

  >>> _shlex_split('a=5 b="15" name="Georgette A"')
  ['a=5', ' ', 'b="15"', ' ', 'name="Georgette A"']

  >>> _shlex_split('a = a5 b=#b19 name="foo bar" q="hi"')
  ['a = a5', ' ', 'b=#b19', ' ', 'name="foo bar"', ' ', 'q="hi"']
  """

  ans = []
  i = 0
  while i < len(s):
    c = s[i]
    if c in string.whitespace:
      # Whitespace.  Add whitespace while found.
      for i2 in range(i, len(s)):
        if s[i2] not in string.whitespace:
          break
      # Include the entire string if the last char is whitespace.
      if s[i2] in string.whitespace:
        i2 += 1
      ans.append(s[i:i2])
      i = i2
    else:
      # Match 'name = "value"'
      c = re.compile(r'\S+\s*\=\s*"[^"]*"')
      m = c.match(s, i)
      if m:
        ans.append(s[i:m.end()])
        i = m.end()
        continue

      # Match 'name = value'
      c = re.compile(r'\S+\s*\=\s*\S*')
      m = c.match(s, i)
      if m:
        ans.append(s[i:m.end()])
        i = m.end()
        continue

      # Match 'name'
      c = re.compile(r'\S+')
      m = c.match(s, i)
      if m:
        ans.append(s[i:m.end()])
        i = m.end()
        continue
  return ans
  
def _test_shlex_split():
  """
  Unit test for _shlex_split().
  """
  assert _shlex_split('') == []
  assert _shlex_split(' ') == [' ']
  assert _shlex_split('a=5 b="15" name="Georgette A"') ==            \
         ['a=5', ' ', 'b="15"', ' ', 'name="Georgette A"']
  assert _shlex_split('a=cvn b=32vsd  c= 234jk\te d \t="hi"') ==     \
         ['a=cvn', ' ', 'b=32vsd', '  ', 'c= 234jk', '\t', 'e', ' ',
          'd \t="hi"']
  assert _shlex_split(' a b c d=e f  g h i="jk" l mno = p  ' +       \
                      'qr = "st"') ==                                \
         [' ', 'a', ' ', 'b', ' ', 'c', ' ', 'd=e', ' ', 'f', '  ',  \
          'g', ' ', 'h', ' ', 'i="jk"', ' ', 'l', ' ', 'mno = p',    \
          '  ', 'qr = "st"']

def _tag_dict(s):
  """
  Helper routine: Extracts dict from an HTML tag string.

  >>> _tag_dict('bgcolor=#ffffff text="#000000" blink')
  ({'bgcolor':'#ffffff', 'text':'#000000', 'blink': None},
   {'bgcolor':(0,7),  'text':(16,20), 'blink':(31,36)},
   {'bgcolor':(8,15), 'text':(22,29), 'blink':(36,36)})

  Returns a 3-tuple.  First element is a dict of
  (key, value) pairs from the HTML tag.  Second element 
  is a dict mapping keys to (start, end) indices of the
  key in the text.  Third element maps keys to (start, end)
  indices of the value in the text.

  Names are lowercased.

  Raises ValueError for unmatched quotes and other errors.
  """
  d = _shlex_split(s)
  attrs     = {}
  key_pos   = {}
  value_pos = {}
  start = 0
  for item in d:
    end = start + len(item)
    equals = item.find('=')
    if equals >= 0:
      # Contains an equals sign.
      (k1, k2) = (start, start + equals)
      (v1, v2) = (start + equals + 1, start + len(item))

      # Strip spaces.
      while k1 < k2 and s[k1] in string.whitespace:   k1 += 1
      while k1 < k2 and s[k2-1] in string.whitespace: k2 -= 1

      while v1 < v2 and s[v1] in string.whitespace:   v1 += 1
      while v1 < v2 and s[v2-1] in string.whitespace: v2 -= 1

      # Strip one pair of quotes around value.
      if v1 < v2 - 1 and s[v1] == '"' and s[v2-1] == '"':
        v1 += 1
        v2 -= 1

      (key, value) = (s[k1:k2].lower(), s[v1:v2])
      attrs[key] = value
      key_pos[key]   = (k1, k2)
      value_pos[key] = (v1, v2)
    elif item.split() == []:
      # Whitespace.  Ignore it.
      pass
    else:
      # A single token, like 'blink'.
      key = item.lower()
      attrs[key]     = None
      key_pos[key]   = (start, end)
      value_pos[key] = (end, end)
    start = end

  return (attrs, key_pos, value_pos)

def _test_tag_dict():
  """
  Unit test for _tag_dict().
  """
  assert _tag_dict('') == ({}, {}, {})
  assert _tag_dict(' \t\r \n\n \r\n  ') == ({}, {}, {})
  assert _tag_dict('bgcolor=#ffffff text="#000000" blink') ==        \
    ({'bgcolor':'#ffffff', 'text':'#000000', 'blink': None},
     {'bgcolor':(0,7),  'text':(16,20), 'blink':(31,36)},
     {'bgcolor':(8,15), 'text':(22,29), 'blink':(36,36)})
  s = ' \r\nbg = val text \t= "hi you" name\t e="5"\t\t\t\n'
  (a, b, c) = _tag_dict(s)
  assert a == {'text': 'hi you', 'bg': 'val', 'e': '5', 'name': None}
  for key in a:
    assert s[b[key][0]:b[key][1]] == key
    if a[key] != None:
      assert s[c[key][0]:c[key][1]] == a[key]

def _full_tag_extract(s):
  """
  Like tagextract(), but different return format.

  Returns a list of _HTMLTag and _TextTag instances.

  The return format is very inconvenient for manipulating HTML, and
  only will be useful if you want to find the exact locations where
  tags occur in the original HTML document.
  """
  L = _html_split(s)

  # Starting position of each L[i] in s.
  Lstart = [0] * len(L)
  for i in range(1, len(L)):
    Lstart[i] = Lstart[i-1] + len(L[i-1])

  class NotTagError(Exception): pass

  for (i, text) in enumerate(L):
    try:

      # Is it an HTML tag?
      is_tag = False
      if len(text) >= 2 and text[0] == '<' and text[-1] == '>':
        # Turn HTML tag text into (name, keyword_dict) tuple.
        is_tag = True
      elif text == _BEGIN_COMMENT or text == _END_COMMENT:
        is_tag = True

      # Ignore text that looks like an HTML tag inside a comment.
      if len(L) > 0 and i > 0 and L[i - 1] == ('!--', {}):
        is_tag = False

      if is_tag:
        # If an HTML tag, strip brackets and handle what's left.

        # Strip off '<>' and update offset.
        orig_offset = 0
        if len(text) >= 1 and text[0] == '<':
          text = text[1:]
          orig_offset = 1
        if len(text) >= 1 and text[-1] == '>':
          text = text[:-1]

        if len(text) > 0 and text[-1] == '/':
          rslash = True
          text = text[:-1]
        else:
          rslash = False

        first_space = text.find(' ')
        if first_space < 0:
          (name, dtext) = (text, '')
        else:
          name  = text[:first_space]
          dtext = text[first_space+1:len(text)]

        # Position of dtext relative to original text.
        dtext_offset = len(name) + 1 + orig_offset    # +1 for space.

        name  = name.strip().lower()
        if rslash:
          name += '/'

        # Strip off spaces, and update dtext_offset as appropriate.
        orig_dtext = dtext
        dtext = dtext.strip()
        dtext_offset += orig_dtext.index(dtext)

        (attrs, key_pos, value_pos) = _tag_dict(dtext)
        # Correct offsets in key_pos and value_pos.
        for key in attrs:
          key_pos[key]   = (key_pos[key][0]+Lstart[i]+dtext_offset,
                            key_pos[key][1]+Lstart[i]+dtext_offset)
          value_pos[key] = (value_pos[key][0]+Lstart[i]+dtext_offset,
                            value_pos[key][1]+Lstart[i]+dtext_offset)
        
        pos = (Lstart[i], Lstart[i] + len(L[i]))
 
        # Wrap inside an _HTMLTag object.
        L[i] = _HTMLTag(pos, name, attrs, key_pos, value_pos)
      else:
        # Not an HTML tag.
        raise NotTagError
    except NotTagError:
      # Wrap non-HTML strings inside a _TextTag object.
      pos = (Lstart[i], Lstart[i] + len(L[i]))
      L[i] = _TextTag(pos, L[i])

  return L


class _HTMLTag:
  """HTML tag extracted by _full_tag_extract()."""
  pos       = property(doc="(start, end) indices of entire tag.")
  name      = property(doc="Name of tag, eg 'img'.")
  attrs     = property(doc="Attribute dict, eg {'href':'http:/X'}")
  key_pos   = property(doc="""
              Key position dict.

              Maps key to (start, end) indices of key.
              """)
  value_pos = property(doc="""
              Value position dict.

              Maps key to (start, end) indices of attrs[key].
              """)

  def __init__(self, pos, name, attrs, key_pos, value_pos):
    """Create an _HTMLTag object."""
    self.pos       = pos
    self.name      = name
    self.attrs     = attrs
    self.key_pos   = key_pos
    self.value_pos = value_pos

class _TextTag:
  """Text extracted from an HTML document by _full_tag_extract()."""
  text = property(doc="Extracted text.")
  pos  = property(doc="(start, end) indices of text.")

  def __init__(self, pos, text):
    """Create a _TextTag object."""
    self.pos  = pos
    self.text = text

# -------------------------------------------------------------------
# URL Editing
# -------------------------------------------------------------------

# Tags within which URLs may be found.
_URL_TAGS = ['a href', 'applet archive', 'applet code',
            'applet codebase', 'area href', 'base href',
            'blockquote cite', 'body background', 'del cite',
            'form action', 'frame longdesc', 'frame src',
            'head profile', 'iframe src', 'iframe longdesc',
            'img src', 'img ismap', 'img longdesc', 'img usemap',
            'input src', 'ins cite', 'link href', 'object archive',
            'object codebase', 'object data', 'object usemap',
            'script src', 'table background', 'tbody background',
            'td background', 'tfoot background', 'th background',
            'thead background', 'tr background']
_URL_TAGS = map(lambda s: tuple(s.split()), _URL_TAGS)


def urlextract(doc, siteurl=None, mimetype='text/html'):
  """
  Extract URLs from HTML or stylesheet.

  Returns a list of L{URLMatch} objects.

  >>> L = urlextract('<img src="a.gif"><a href="www.google.com">')
  >>> L[0].url
  'a.gif'
  >>> L[1].url
  'www.google.com'

  If siteurl is specified, all URLs are made into absolute URLs
  by assuming that 'doc' is located at the URL 'siteurl'.

  >>> doc = '<img src="a.gif"><a href="/b.html">'
  >>> L = urlextract(doc, 'http://www.python.org/~guido/')
  >>> L[0].url
  'http://www.python.org/~guido/a.gif'
  >>> L[1].url
  'http://www.python.org/b.html'

  If mimetype is 'text/css', the document will be parsed
  as a stylesheet.
  """
  mimetype = mimetype.lower()
  if mimetype == 'text/css':
    # Match URLs within CSS stylesheet.
    # Match url(blah) or url("blah").
    L = list(re.finditer(r'url\s*\(([^\r\n\("]*?)\)|' +
                         r'url\s*\(\s*"([^\r\n]*?)"\s*\)', doc))
    L = [(x.start(x.lastindex), x.end(x.lastindex)) for x in L]
    L = [URLMatch(doc, s, e, siteurl, False, True) for (s, e) in L]
    return L
  else:
    # Match URLs within HTML document.
    ans = []
    L = _full_tag_extract(doc)
    item = None
    for i in range(len(L)):
      prev_item = item
      item = L[i]

      # Handle string item (text) or tuple item (tag).
      if isinstance(item, _TextTag):
        # Current item is text.
        if isinstance(prev_item, _HTMLTag) and prev_item.name == \
           'style':
          # And previous item is <style>.  Process a stylesheet.
          temp = urlextract(item.text, siteurl, 'text/css')
          # Offset indices and add to ans.
          for j in range(len(temp)):
            temp[j].start += item.pos[0]
            temp[j].end   += item.pos[0]
          ans += temp
        else:
          # Regular text.  Ignore.
          pass
      else:
        # Current item is a tag.
        for (a, b) in _URL_TAGS:
          if item.name.startswith(a) and b in item.attrs:
            # Got one URL.
            url = item.attrs[b]
            # FIXME: Some HTML tag wants a URL list, look up which
            # tag and make it a special case.
            (start, end) = item.value_pos[b]
            tag_name  = a
            tag_attr  = b
            tag_attrs = item.attrs
            tag_index = i
            tag = URLMatch(doc, start, end, siteurl, True, False,    \
                           tag_attr, tag_attrs, tag_index, tag_name)
            ans.append(tag)
    return ans
    # End of 'text/html' mimetype case.

def _tuple_replace(s, Lindices, Lreplace):
  """
  Replace slices of a string with new substrings.

  Given a list of slice tuples, replace those slices in 's'
  with corresponding replacement substrings from 'Lreplace'.

  Example:

  >>> _tuple_replace('0123456789',[(4,5),(6,9)],['abc', 'def'])
  '0123abc5def9'
  """
  ans = []
  Lindices = Lindices[:]
  Lindices.sort()
  if len(Lindices) != len(Lreplace):
    raise ValueError('lists differ in length')
  for i in range(len(Lindices)-1):
    if Lindices[i][1] > Lindices[i+1][0]:
      raise ValueError('tuples overlap')
    if Lindices[i][1] < Lindices[i][0]:
      raise ValueError('invalid tuple')
    if min(Lindices[i][0], Lindices[i][1]) < 0 or                    \
       max(Lindices[i][0], Lindices[i][1]) >= len(s):
      raise ValueError('bad index')

  j = 0
  offset = 0
  for i in range(len(Lindices)):
    
    len1 = Lindices[i][1] - Lindices[i][0]
    len2 = len(Lreplace[i])

    ans.append(s[j:Lindices[i][0]+offset])
    ans.append(Lreplace[i])

    j = Lindices[i][1]
  ans.append(s[j:])
  return ''.join(ans)

def _test_tuple_replace():
  """
  Unit test for _tuple_replace().
  """
  assert _tuple_replace('',[],[]) == ''
  assert _tuple_replace('0123456789',[],[]) == '0123456789'
  assert _tuple_replace('0123456789',[(4,5),(6,9)],['abc', 'def'])== \
         '0123abc5def9'
  assert _tuple_replace('01234567890123456789',                      \
         [(1,9),(13,14),(16,18)],['abcd','efg','hijk']) ==           \
         '0abcd9012efg45hijk89'

def urljoin(s, L):
  """
  Write back document with modified URLs (reverses urlextract).

  Given a list 'L' of URLMatch objects obtained from
  urlextract(), substitutes changed URLs into the original
  document 's', and returns the modified document.  One should only
  modify the .url attribute of the URLMatch objects.

  >>> doc = '<img src="a.png"><a href="b.png">'
  >>> L = urlextract(doc)
  >>> L[0].url = 'foo'
  >>> L[1].url = 'bar'
  >>> urljoin(doc, L)
  '<img src="foo"><a href="bar">'
  
  """
  return _tuple_replace(s, [(x.start, x.end) for x in L],            \
                           [x.url for x in L])

class URLMatch:
  url     = property(doc="URL extracted.")
  start   = property(doc="Starting character index.")
  end     = property(doc="End character index.")
  in_html = property(doc="True if URL occurs within an HTML tag.")
  in_css  = property(doc="True if URL occurs within a stylesheet.")

  tag_attr  = property(doc="""
              Specific tag attribute in which URL occurs.

              Example: 'href'.
              None if the URL does not occur within an HTML tag.
              """)
  tag_attrs = property(doc="""
              Dictionary of all tag attributes and values.

              Example: {'src':'http://X','alt':'Img'}.
              None if the URL does not occur within an HTML tag.
              """)
  tag_index = property(doc="""
              Index of the tag in tagextract(doc).

              None if the URL does not occur within an HTML tag.
              """)
  tag_name  = property(doc="""
              HTML tag name in which URL occurs.

              Example: 'img'.
              None if the URL does not occur within an HTML tag.
              """)

  def __init__(self, doc, start, end, siteurl, in_html, in_css,
               tag_attr=None, tag_attrs=None, tag_index=None,
               tag_name=None):
    """
    Create a URLMatch object.
    """
    self.doc     = doc
    self.start   = start
    self.end     = end
    self.url     = doc[start:end]
    self.in_html = in_html
    self.in_css  = in_css

    if siteurl != None:
      self.url = urlparse.urljoin(siteurl, self.url)

    self.tag_attr = tag_attr

# -------------------------------------------------------------------
# Unit Tests: HTML <-> Data structure
# -------------------------------------------------------------------

def _test_tagextract():
  """
  Unit tests for tagextract() and tagjoin().
  """

  # Simple HTML document to test.
  doc1 = '\n\n<Html><BODY bgcolor=#ffffff>Hi<h1>Ho</h1><br>' +       \
         '<br /><img SRc="text%5f.gif"><TAG NOshow>'         +       \
         '<img test="5%ff" /></body></html>\nBye!\n'
  doc2 = '\r<HTML><!-- Comment<a href="blah"> --><hiYa><foo>' +      \
         '<test tag="5" content=6><is broken=False><yay>'     +      \
         '<style><><>><</style><foo bar=5>end<!-- <!-- nested --> '+ \
         '<script language="JavaScript"><>!><!_!_!-->!_-></script>'
  doc3 = '\r\t< html >< tag> <!--comment--> <tag a = 5> '     +      \
         '<foo \r\nbg = val text \t= "hi you" name\t e="5"\t\t\t\n>'

  # -----------------------------------------------------------------
  # Test _html_split()
  # -----------------------------------------------------------------

  s = doc1
  assert s == ''.join(_html_split(s))
  assert _html_split(s) ==                                           \
  ['\n\n', '<Html>', '<BODY bgcolor=#ffffff>', 'Hi', '<h1>', 'Ho',   \
   '</h1>', '<br>', '<br />', '<img SRc="text%5f.gif">',             \
   '<TAG NOshow>', '<img test="5%ff" />', '</body>', '</html>',      \
   '\nBye!\n']

  s = doc2
  assert s == ''.join(_html_split(s))

  s = '<!-- test weird comment <body> <html> --> <h1>Header' +       \
      '</h1 value=10 a=11>'
  assert s == ''.join(_html_split(s))
  assert _html_split(s) ==                                           \
  ['<!--', ' test weird comment <body> <html> ', '-->', ' ',         \
   '<h1>', 'Header', '</h1 value=10 a=11>']

  s = '<!-- <!-- nested messed up --> blah ok <now> what<style>hi' + \
      '<><>></style><script language="Java"><aL><>><>></script>a'
  assert s == ''.join(_html_split(s))
  assert _html_split(s) ==                                           \
  ['<!--', ' <!-- nested messed up ', '-->', ' blah ok ', '<now>',   \
   ' what', '<style>', 'hi<><>>', '</style>',                        \
   '<script language="Java">', '<aL><>><>>', '</script>', 'a']

  s = '<!-- ><# -->!<!-!._-><!-- aa--> <style><tag//</style> <tag '+ \
      '<tag <! <! -> <!-- </who< <who> tag> <huh-->-</style>'      + \
      '</style<style>'
  assert s == ''.join(_html_split(s))
  assert _html_split(s) ==                                           \
  ['<!--', ' ><# ', '-->', '!', '<!-!._->', '<!--', ' aa', '-->',    \
   ' ', '<style>', '<tag//', '</style>', ' ', '<tag <tag <! <! ->',  \
   ' ', '<!--', ' </who< <who> tag> <huh', '-->', '-', '</style>',   \
   '</style<style>']

  # -----------------------------------------------------------------
  # Test tagextract() and tagjoin()
  # -----------------------------------------------------------------

  s = doc1
  assert tagextract('') == []
  assert tagextract(s) ==                                            \
         ['\n\n', ('html', {}), ('body', {'bgcolor': '#ffffff'}),    \
          'Hi', ('h1', {}), 'Ho', ('/h1', {}), ('br', {}),           \
          ('br/', {}), ('img', {'src': 'text%5f.gif'}),              \
          ('tag', {'noshow': None}), ('img/', {'test': '5%ff'}),     \
          ('/body', {}), ('/html', {}), '\nBye!\n']
  s2 = '\n\n<html><body bgcolor="#ffffff">Hi<h1>Ho</h1><br>' +       \
       '<br /><img src="text%5f.gif"><tag noshow>' +                 \
       '<img test="5%ff" /></body></html>\nBye!\n'
  assert tagjoin(tagextract(s)) == s2


  doc2old = doc2
  doc2 = '\r<HTML><!-- Comment<a href="blah"> --><hiYa><foo>' +      \
         '<test tag="5" content=6><is broken=False><yay>'     +      \
         '<style><><>><</style><foo bar=5>end<!-- <!-- nested --> '+ \
         '<script language="JavaScript"><>!><!_!_!-->!_-></script>'
  assert doc2old == doc2 # FIXME

  s = doc2
  assert tagextract(s) ==                                            \
  ['\r', ('html', {}), ('!--', {}), ' Comment<a href="blah"> ',      \
  ('--', {}), ('hiya', {}), ('foo', {}),                             \
  ('test', {'content': '6', 'tag': '5'}),                            \
  ('is', {'broken': 'False'}), ('yay', {}), ('style', {}), '<><>><', \
  ('/style', {}), ('foo', {'bar': '5'}), 'end', ('!--', {}),         \
  ' <!-- nested ', ('--', {}), ' ',                                  \
  ('script', {'language': 'JavaScript'}), ('>!><!_!_!-->!_-', {}),   \
  ('/script', {})]

  assert tagjoin(tagextract(s)) ==                                   \
  '\r<html><!-- Comment<a href="blah"> --><hiya><foo><test ' +       \
  'content="6" tag="5"><is broken="False"><yay><style><><>><' +      \
  '</style><foo bar="5">end<!-- <!-- nested --> ' +                  \
  '<script language="JavaScript"><>!><!_!_!-->!_-></script>'

  # -----------------------------------------------------------------
  # Test _full_tag_extract()
  # -----------------------------------------------------------------

  for s in [doc1, doc2, doc3]:
    L = _full_tag_extract(s)
    for (i, item) in enumerate(L):
      if isinstance(item, _HTMLTag):
        for key in item.attrs:
          assert s[item.key_pos[key][0]:item.key_pos[key][1]].lower()\
                 == key
          if item.attrs[key] != None:
            assert s[item.value_pos[key][0]:item.value_pos[key][1]]  \
                   == item.attrs[key]

  n = 1000
  doc4 = '<tag name = "5" value ="6afdjherknc4 cdk j" a="7" b=8/>'*n
  L = tagextract(doc4)
  assert len(L) == n
  for i in range(n):
    assert L[i] == ('tag/',{'name':'5','value':'6afdjherknc4 cdk j', \
                           'a':'7', 'b':'8'})

# -------------------------------------------------------------------
# Unit Tests: URL Parsing
# -------------------------------------------------------------------

def _test_urlextract():
  """
  Unit tests for urlextract() and urljoin().
  """

  doc1 = 'urlblah, url ( blah2, url( blah3) url(blah4) ' +           \
         'url("blah5") hum("blah6") url)"blah7"( url ( " blah8 " );;'
  doc2 = '<html><img src="a.gif" alt="b"><a href = b.html name='  + \
      '"c"><td background =  ./c.png width=100%><a value=/f.jpg>' + \
      '<img src="http://www.abc.edu/d.tga">http://www.ignore.us/' + \
      '\nhttp://www.nowhere.com <style>url(h.gif) '               + \
      'url(http://www.testdomain.com/) http://ignore.com/a'       + \
      '</style><img alt="c" src = "a.gif"><img src=/i.png>'

  # Test CSS.
  s = doc1
  L = urlextract(s, mimetype='text/css')
  L2 = [x.url for x in L]
  assert L2 == [' blah3', 'blah4', 'blah5', ' blah8 ']

  # Test HTML.
  s = doc2
  L = urlextract(s)
  L2 = [x.url for x in L]
  ans = ['a.gif', 'b.html', './c.png',                              \
                'http://www.abc.edu/d.tga', 'h.gif',                \
                'http://www.testdomain.com/', 'a.gif', '/i.png']
  assert L2 == ans

  for i in range(len(L)):
    assert s[L[i].start:L[i].end] == L[i].url

  # Test HTML more.
  n = 100
  s2 = s * n

  L3 = urlextract(s2)
  L4 = [x.url for x in L3]
  assert L4 == L2 * n
  for i in range(len(L3)):
    assert s2[L3[i].start:L3[i].end] == L3[i].url

  # Test HTML w/ siteurl.
  base = 'http://www.python.org/~guido/'
  L = urlextract(s, base)
  L2 = [x.url for x in L]
  assert L2 == [urlparse.urljoin(base, x) for x in ans]

  # Test urljoin().
  assert urljoin(doc1, urlextract(doc1, mimetype='text/css')) == doc1
  assert urljoin(doc2, urlextract(doc2)) == doc2

  s = doc2
  L = urlextract(s)
  L[3].url = 'FOO'
  L[5].url = 'BAR'
  L[7].url = 'F00!'
  assert urljoin(s, L) ==                                            \
  '<html><img src="a.gif" alt="b"><a href = b.html name="c">' +      \
  '<td background =  ./c.png width=100%><a value=/f.jpg>' +          \
  '<img src="FOO">http://www.ignore.us/\nhttp://www.nowhere.com ' +  \
  '<style>url(h.gif) url(BAR) http://ignore.com/a</style>' +         \
  '<img alt="c" src = "a.gif"><img src=F00!>'

# -------------------------------------------------------------------
# Unit Test Main Routine
# -------------------------------------------------------------------

def _test():
  """
  Unit test main routine.
  """
  print 'Unit tests:'
  _test_shlex_split()
  print '  _shlex_split:           OK'
  _test_tag_dict()
  print '  _tag_dict:              OK'
  _test_tuple_replace()
  print '  _tuple_replace:         OK'
  _test_tagextract()
  print '  tagextract:             OK'
  print '  tagjoin:                OK'
  _test_urlextract()
  print '  urlextract:             OK'
  print '  urljoin:                OK'

if __name__ == '__main__':
  _test()
