"""
Manipulate HTML documents via data structure.

Version 1.0.0.  This source code has been placed in the
public domain by Connelly Barnes.
"""

import shlex
import string
import urllib

# Translate text between these strings as plain text (not HTML).
IGNORE_TAGS = [('script', '/script'),
               ('style',  '/style'),
               ('pre', '/pre')]

BEGIN_COMMENT = '<!--'
END_COMMENT   = '-->'


def _ignore_tag_index(s, i):
  """
  Find index within IGNORE_TAGS, or -1.

  If s[i:] begins with an opening tag from IGNORE_TAGS, return the
  index.  Otherwise, return -1.
  """
  for (j, (a, b)) in enumerate(IGNORE_TAGS):
    if s[i:i+len(a)+1].lower() == '<' + a:
      return j
  return -1

def _html_split(s):
  """
  Split string 's' into a list 'L' of tags and non-tags.

  >>> html_split(' blah <tag text> more </tag stuff> ')
  [' blah ', '<tag text>', ' more ', '</tag stuff>', ' ']

  Tags begin with '<' and end with '>'.   Also, ''.join(L) == s.

  Special exceptions:

  '<script>', '<pre>', and HTML comment tags ignore all HTML
  until the closing pair, and are added as three elements:

  >>> html_split(' blah<pre><<<><></pre><!-- comment -->' + \
                 ' <script language="Javascript"></>a</script>end')
  [' blah', '<pre>', '<<<><>', '</pre>', '<!--', ' comment ', '-->',\
   ' ', '<script language="Javascript">', '</>a', '</script>', 'end']

  """
  s_lower = s.lower()
  L = []

  i = 0               # Index of char being processed
  while i < len(s):
    c = s[i]
    if c == '<':
      # Left bracket, handle various cases.
      if s[i:i+len(BEGIN_COMMENT)].startswith(BEGIN_COMMENT):
        # HTML begin comment tag, '<!--'.  Scan for '-->'.
        L.append(BEGIN_COMMENT)
        i += len(BEGIN_COMMENT)
        i2 = s.find(END_COMMENT, i)
        if i2 < 0:
          # No '-->'.  Append the rest as text.
          L.append(s[i:])
          break
        else:
          # Append the comment text.
          L.append(s[i:i2])
          # Then append the '-->' as a tag.
          L.append(s[i2:i2+len(END_COMMENT)])
          i = i2 + len(END_COMMENT)
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

        # Check whether we processed a special ignore tag, eg '<pre>'
        tagi = _ignore_tag_index(s, orig_i)
        if tagi >= 0:
          # It's an ignore tag.  Scan for the end tag.
          i2 = s_lower.find('<' + IGNORE_TAGS[tagi][1], i)
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

def _tag_dict(s):
  """
  Extracts dict from an HTML tag string.

  >>> _tag_dict('bgcolor=#ffffff text="#000000" blink')
  {'bgcolor':'#ffffff', 'text':'#000000', 'blink': None}

  Encoded %XX hex codes in the values are unescaped.  Names
  are lowercased.

  Raises ValueError for unmatched quotes and other errors.
  """
  d = shlex.split(s)
  ans = {}
  for item in d:
    equals = item.find('=')
    if equals >= 0:
      (key, value) = (item[:equals].lower(), item[equals+1:])
      value = urllib.unquote(value)
      ans[key] = value
    else:
      ans[item.lower()] = None
  return ans

def loads(s):
  """
  Load an HTML string into a data structure.

  Returns a list.  HTML tags become (name, keyword_dict) tuples
  within the list, while plain text becomes strings within the
  list.  All tag names are lowercased and stripped of whitespace.
  Tags which end with forward slashes have a single forward slash
  placed at the end of their name, to indicate that they are XML
  unclosed tags.

  Example:

  >>> loads('abc<body bgcolor=#ffffff>Hi<h1>Ho</h1><br>a<br/>Bye!')
  ['abc', ('body', {'bgcolor': '#ffffff'}), 'Hi', ('h1', {}),
  'Ho', ('/h1', {}), ('br', {}), 'a', ('br/', {}), 'Bye!']

  Text between '<script>', '<style>', and '<pre>' tags is rendered
  directly to plain text. This prevents rogue '<' or '>' characters
  from interfering with parsing.

  >>> loads('<script language="Javascript"><blah>var x; </script>')
  [('script', {'language': 'Javascript'}), '<blah>var x; ',
   ('/script', {})]

  Text inside the comment strings '<!--' and '-->' is also rendered
  as plain text.  The opening and closing comments are translated
  into ('!--', {}) and ('--', {}), respectively.

  Example:

  >>> loads('<!-- blah -->')
  ['!--', ' blah ', '--']

  If an HTML string is turned into a data structure, then back into
  HTML, the resulting string will be functionally equivalent to the
  original HTML.

  >>> dumps(loads(s))
  (string that is functionally equivalent to s)

  Three changes are made to the HTML by dumps(): tags are lowercased,
  key=value pairs are sorted, and values are placed in double-quotes.

  """
  L = _html_split(s)
  for (i, text) in enumerate(L):
    try:

      # Is it an HTML tag?
      is_tag = False
      if len(text) >= 2 and text[0] == '<' and text[-1] == '>':
        # Turn HTML tag text into (name, keyword_dict) tuple.
        is_tag = True
      elif text == BEGIN_COMMENT or text == END_COMMENT:
        is_tag = True

      if is_tag:
        # If an HTML tag, strip brackets and handle what's left.
        text = text.strip('<>')
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

        name  = name.strip().lower()
        if rslash:
          name += '/'
        dtext = dtext.strip()

        d = _tag_dict(dtext)
        L[i] = (name, d)
      else:
        # Not an HTML tag.
        raise ValueError
    except ValueError:
      # Leave non-HTML strings as they are.
      pass
  return L

def dumps(L):
  """
  Dump an HTML data structure into an HTML string.

  This reverses the loads() function.
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
          tag_items.append(key + '="' + urllib.quote(value) + '"')
        else:
          tag_items.append(key)
      tag_items = ' '.join(tag_items)
      if tag_items != '':
        tag_items = ' ' + tag_items
      ans.append('<' + name + tag_items + rslash + '>')
  return ''.join(ans)

def test():
  """
  Unit test for loads() and dumps().
  """

  # Simple HTML document to test.
  doc1 = '\n\n<Html><BODY bgcolor=#ffffff>Hi<h1>Ho</h1><br>' +       \
         '<br /><img SRc="text%5f.gif"><TAG NOshow>'         +       \
         '<img test="5%ff" /></body></html>\nBye!\n'
  doc2 = '\r<HTML><!-- Comment<a href="blah"> --><hiYa><foo>' +      \
         '<test tag="5" content=6><is broken=False><yay>'     +      \
         '<pre><><>><</pre><foo bar=5>end<!-- <!-- nested --> ' +    \
         '<script language="JavaScript"><>!><!_!_!-->!_-></script>'

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

  s = '<!-- <!-- nested messed up --> blah ok <now> what<pre>hi' +   \
      '<><>></pre><script language="Javascript"><aL><>><>></script>a'
  assert s == ''.join(_html_split(s))
  assert _html_split(s) ==                                           \
  ['<!--', ' <!-- nested messed up ', '-->', ' blah ok ', '<now>',   \
   ' what', '<pre>', 'hi<><>>', '</pre>',                            \
   '<script language="Javascript">', '<aL><>><>>', '</script>', 'a']

  s = '<!-- ><# -->!<!-!._-><!-- aa--> <pre><tag//</pre> <tag ' +    \
      '<tag <! <! -> <!-- </who< <who> tag> <huh-->-</pre></pre<pre>'
  assert s == ''.join(_html_split(s))
  assert _html_split(s) ==                                           \
  ['<!--', ' ><# ', '-->', '!', '<!-!._->', '<!--', ' aa', '-->',    \
   ' ', '<pre>', '<tag//', '</pre>', ' ', '<tag <tag <! <! ->',      \
   ' ', '<!--', ' </who< <who> tag> <huh', '-->', '-', '</pre>',     \
   '</pre<pre>']

  # -----------------------------------------------------------------
  # Test loads() and dumps()
  # -----------------------------------------------------------------

  s = doc1
  assert loads('') == []
  assert loads(s) ==                                                 \
         ['\n\n', ('html', {}), ('body', {'bgcolor': '#ffffff'}),    \
          'Hi', ('h1', {}), 'Ho', ('/h1', {}), ('br', {}),           \
          ('br/', {}), ('img', {'src': 'text_.gif'}),                \
          ('tag', {'noshow': None}), ('img/', {'test': '5\xff'}),    \
          ('/body', {}), ('/html', {}), '\nBye!\n']
  s2 = '\n\n<html><body bgcolor="%23ffffff">Hi<h1>Ho</h1><br>' +     \
       '<br /><img src="text_.gif"><tag noshow>' +                   \
       '<img test="5%FF" /></body></html>\nBye!\n'
  assert dumps(loads(s)) == s2


  doc2 = '\r<HTML><!-- Comment<a href="blah"> --><hiYa><foo>' +      \
         '<test tag="5" content=6><is broken=False><yay>'     +      \
         '<pre><><>><</pre><foo bar=5>end<!-- <!-- nested --> ' +    \
         '<script language="JavaScript"><>!><!_!_!-->!_-></script>'

  s = doc2
  assert loads(s) ==                                                 \
  ['\r', ('html', {}), ('!--', {}), ' Comment<a href="blah"> ',      \
  ('--', {}), ('hiya', {}), ('foo', {}),                             \
  ('test', {'content': '6', 'tag': '5'}),                            \
  ('is', {'broken': 'False'}), ('yay', {}), ('pre', {}), '<><>><',   \
  ('/pre', {}), ('foo', {'bar': '5'}), 'end', ('!--', {}),           \
  ' <!-- nested ', ('--', {}), ' ',                                  \
  ('script', {'language': 'JavaScript'}), ('!><!_!_!-->!_-', {}),    \
  ('/script', {})]

  assert dumps(loads(s)) ==                                          \
  '\r<html><!-- Comment<a href="blah"> --><hiya><foo><test ' +       \
  'content="6" tag="5"><is broken="False"><yay><pre><><>><</pre>' +  \
  '<foo bar="5">end<!-- <!-- nested --> '                         +  \
  '<script language="JavaScript"><!><!_!_!-->!_-></script>'

  print 'Unit test passed.'

if __name__ == '__main__':
  test()
