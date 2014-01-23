# encoding: utf-8
"""
colors.themes

"""

from __future__ import with_statement, division
import sys
import os
import sqlite3
import json
import time
from os.path import basename, dirname, abspath, splitext, join, isdir, exists
from collections import OrderedDict as odict
from random import random
from glob import glob
from zipfile import ZipFile
from contextlib import contextmanager
py_root = dirname(abspath(__file__))
_mkdir = lambda pth: exists(pth) or os.makedirs(pth)
from pprint import pprint

#### COLOR AGGREGATE #################################################################################

from nodebox.graphics.colors import CONFIG_DIR, named_hues, named_colors, named_color, color, shade, colorlist

DEFAULT_DB = join(CONFIG_DIR, "themes.db")

class ColorThemeNotFound(Exception): pass

class ColorTheme(list):
    
    def __init__(self, name="", ranges=[], top=5, cache=None, blue="blue", guess=False, length=100):

        """ A set of weighted ranges linked to colors.
        
        A ColorTheme is a set of allowed colors (e.g. red, black)
        and ranges (e.g. dark, intense) for these colors.
        These are supplied as lists of (color, range, weight) tuples.
        Ranges with a greater weight will occur more in the combined range.
        
        A ColorTheme is expected to have a name,
        so it can be stored and retrieved in the XML cache.
        
        The blue parameter denotes a color correction.
        Since most web aggregated results will yield "blue" instead of "azure" or "cyan",
        we may never see these colors (e.g. azure beach will not propagate).
        So instead of true blue we pass "dodgerblue", which will yield more all-round shades of blue.
        To ignore this, set blue="blue".
        
        """

        self.name = name
        self.ranges = []
        self.cache = cache
        self.top = top
        self.tags = []
        self.blue = blue
        self.db = ColorThemeDB()
        self.guess = False
        self.length = 100
        
        self.group_swatches = False

        # See if we can load data from cache first.
        if not self.cache or self.cache in self.db.collections:
            if self._load(top, blue):
                self.tags.append(name)
                self.group_swatches = True
                return

        # Otherwise, we expect some parameters to specify the data.
        if len(ranges) > 0:
            self.ranges = ranges

        # Nothing in the cache matches the query
        # and no parameters were specified, so we're going to guess.
        # This works reasonably well for obvious things like
        # abandon -> abandoned, frail -> fragile
        if len(self.ranges) == 0 and guess:
            m = difflib.get_close_matches(self.name, self.db.queries(self.cache), cutoff=0.8)
            if len(m) > 0:
                self.name = m[0]
                self._load(top, blue)
                self.tags.append(self.name)
                self.group_swatches = True
                self.guess = True

        if self.name != "" and len(self.ranges) == 0:
            raise ColorThemeNotFound

    def add_range(self, range, clr=None, weight=1.0):
        
        # You can also supply range and color as a string,
        # e.g. "dark ivory".
        if isinstance(range, str) and clr == None:
            for word in range.split(" "):
                if word in named_hues \
                or word in named_colors:
                    clr = named_color(word)
                if shade(word) != None:
                    range = shade(word)
                    
        self.ranges.append((color(clr), range, weight))

    def copy(self):
        
        t = ColorTheme(
            name = self.name,
            ranges = [(clr.copy(), rng.copy(), wgt) for clr, rng, wgt in self],
            top = self.top,
            cache = self.cache,
            blue = self.blue,
            guess = self.guess,
            lenght = self.length
        )
        t.tags = self.tags
        t.group_swatches = self.group_swatches
        return t
        
    def _weight_by_hue(self):
        
        """ Returns a list of (hue, ranges, total weight, normalized total weight)-tuples.
        
        ColorTheme is made up out of (color, range, weight) tuples.
        For consistency with XML-output in the old Prism format
        (i.e. <color>s made up of <shade>s) we need a group
        weight per different hue.
        
        The same is true for the swatch() draw method.
        Hues are grouped as a single unit (e.g. dark red, intense red, weak red)
        after which the dimensions (rows/columns) is determined.
        
        """
        
        grouped = {}
        weights = []
        for clr, rng, weight in self.ranges:
            h = clr.nearest_hue(primary=False)
            if grouped.has_key(h):
                ranges, total_weight = grouped[h]
                ranges.append((clr, rng, weight))
                total_weight += weight
                grouped[h] = (ranges, total_weight)
            else:
                grouped[h] = ([(clr, rng, weight)], weight)

        # Calculate the normalized (0.0-1.0) weight for each hue,
        # and transform the dictionary to a list.
        s = 1.0 * sum([w for r, w in grouped.values()])
        grouped = [(grouped[h][1], grouped[h][1]/s, h, grouped[h][0]) for h in grouped]
        grouped.sort()
        grouped.reverse()

        return grouped
    @property
    def json(self):
      """ Returns the color information as json.
      {"query":"search term",
       "theme":{
          "green":{
            "weight": 0.01,
            "shades":{
              "neutral": 0.1,
              "fresh": 0.2,
              "warm": 0.3,
            }
          },
          "blue":{...},
          ...
        }
      }
      """
      clrs = {}
      grouped = self._weight_by_hue()
      for total_weight, normalized_weight, hue, ranges in grouped:
          if hue == self.blue: hue = "blue"
          clr = color(hue)
          shds = {str(rng):wgt/total_weight for _,rng,wgt in ranges}
          clrs[clr.name] = {"weight":normalized_weight, "shades":shds}
          # clrs[clr.name].update({"rgb":[clr.r, clr.g, clr.b]})
      return clrs

    @property
    def xml(self):

        """ Returns the color information as XML.
        
        The XML has the following structure:
        <colors query="">
            <color name="" weight="" />
                <rgb r="" g="" b="" />
                <shade name="" weight="" />
            </color>
        </colors>
        
        Notice that ranges are stored by name and retrieved in the _load()
        method with the shade() command - and are thus expected to be
        shades (e.g. intense, warm, ...) unless the shade() command would
        return any custom ranges as well. This can be done by appending custom
        ranges to the shades list.
        
        """

        grouped = self._weight_by_hue()
        
        xml = "<colors query=\""+self.name+"\" tags=\""+", ".join(self.tags)+"\">\n\n"
        for total_weight, normalized_weight, hue, ranges in grouped:
            if hue == self.blue: hue = "blue"
            clr = color(hue)
            xml += "\t<color name=\""+clr.name+"\" weight=\""+str(normalized_weight)+"\">\n "
            xml += "\t\t<rgb r=\""+str(clr.r)+"\" g=\""+str(clr.g)+"\" "
            xml += "b=\""+str(clr.b)+"\" a=\""+str(clr.a)+"\" />\n "
            for clr, rng, wgt in ranges:
                xml += "\t\t<shade name=\""+str(rng)+"\" weight=\""+str(wgt/total_weight)+"\" />\n "
            xml = xml.rstrip(" ") + "\t</color>\n\n"
        xml += "</colors>"
        
        return xml

    def _save(self):
        
        """ Saves the color information to the DB.
        """

        # print "update", self.name, self.cache, self.json
        self.db.update(self.name, self.cache, self.json)

        # if not os.path.exists(self.cache):
        #     os.makedirs(self.cache)
        
        # path = os.path.join(self.cache, self.name+".xml")
        # f = open(path, "w")
        # f.write(self.xml)
        # f.close()
    
    def _load(self, top=5, blue="blue"):

        """ Loads a theme from aggregated web data.
       
        The data must be old-style Prism XML: <color>s consisting of <shade>s.
        Colors named "blue" will be overridden with the blue parameter.
        
        """
        
        self.cache, theme = self.db.query(self.name, self.cache)
        for name, mixture in theme.items()[:top]:
            if name == "blue": name = blue
            w = mixture['weight']
            clr = color(name)
            for name, weight in mixture['shades'].items():
                self.ranges.append( (clr, shade(name), w*weight) )
        return bool(theme)
                
    def color(self, d=0.035):

        """ Returns a random color within the theme.
        
        Fetches a random range (the weight is taken into account,
        so ranges with a bigger weight have a higher chance of propagating)
        and hues it with the associated color.
        
        """

        s = sum([w for clr, rng, w in self.ranges])
        r = random()
        for clr, rng, weight in self.ranges:
            if weight/s >= r: break
            r -= weight/s
        
        return rng(clr, d)  
        
    def colors(self, n=10, d=0.035):
      
        """ Returns a number of random colors from the theme.
        """
      
        s = sum([w for clr, rng, w in self.ranges])
        colors = colorlist()
        for i in range(n):
            r = random()
            for clr, rng, weight in self.ranges:
                if weight/s >= r: break
                r -= weight/s
            colors.append(rng(clr, d))
        
        return colors
    
    colorlist = colors

    def contains(self, clr):
        for c, rng, weight in self.ranges:
            if clr in rng: return True
        return False
    
    # You can do: if clr in aggregate.
    
    def __contains__(self, clr):
        return self.contains(clr)

    # Behaves as a list.

    def __len__(self):
        return self.length
    
    def __getitem__(self, i):
        return self.color()
        
    def __getslice__(self, i, j):
        j = min(len(self), j)
        n = min(len(self), j-i)
        return colorlist([self.color() for i in range(n)])
    
    def __iter__(self):
        colors = [self.color() for i in range(len(self))]
        return iter(colors)
    
    # You can do + and += operations.
    
    def __add__(self, theme):
        t = self.copy()
        t.ranges.extend(theme.ranges)
        t.tags.extend(theme.tags)
        return t
        
    def __iadd__(self, theme):
        return self.__add__(theme)
        
    # Callable as a stateless function.
    
    def __call__(self, n=1, d=0.035):
        if n > 1:
            return self.colors(n, d)
        else:
            return self.color(d)
        
    # Behaves as a string.
    
    def __str__(self):
        return self.name
    
    def __repr__(self):
        return self.name
    
    def recombine(self, other, d=0.7):
        
        """ Genetic recombination of two themes using cut and splice technique.
        """
        
        a, b = self, other
        d1  = max(0, min(d, 1))
        d2 = d1
        
        c = ColorTheme(
            name = a.name[:int(len(a.name)*d1) ] + 
                   b.name[ int(len(b.name)*d2):],
            ranges = a.ranges[:int(len(a.ranges)*d1) ] + 
                     b.ranges[ int(len(b.ranges)*d2):],
            top = a.top,
            cache = "recombined",
            blue = a.blue,
            length = a.length*d1 + b.length*d2
        )
        c.tags  = a.tags[:int(len(a.tags)*d1) ] 
        c.tags += b.tags[ int(len(b.tags)*d2):]
        return c

    def swatch(self, x, y, w=35, h=35, padding=4, roundness=0, n=12, d=0.035, grouped=None):
        
        """ Draws a weighted swatch with approximately n columns and rows.
        
        When the grouped parameter is True, colors are grouped in blocks of the same hue
        (also see the _weight_by_hue() method).
        
        """
        
        if grouped == None: # should be True or False
            grouped = self.group_swatches
        
        # If we dont't need to make groups,
        # just display an individual column for each weight
        # in the (color, range, weight) tuples.
        if not grouped:
            s = sum([wgt for clr, rng, wgt in self.ranges])
            for clr, rng, wgt in self.ranges:
                cols = max(1, int(wgt/s*n))
                for i in range(cols):
                    rng.colors(clr, n=n, d=d).swatch(x, y, w, h, padding=padding, roundness=roundness)
                    x += w+padding
            
            return x, y+n*(h+padding)
        
        # When grouped, combine hues and display them
        # in batches of rows, then moving on to the next hue.
        grouped = self._weight_by_hue()
        for total_weight, normalized_weight, hue, ranges in grouped:
            dy = y
            rc = 0
            for clr, rng, weight in ranges:
                dx = x
                cols = int(normalized_weight*n)
                cols = max(1, min(cols, n-len(grouped)))
                if clr.name == "black": rng = rng.black
                if clr.name == "white": rng = rng.white
                for i in range(cols):
                    rows = int(weight/total_weight*n)
                    rows = max(1, rows)
                    # Each column should add up to n rows,
                    # if not due to rounding errors, add a row at the bottom.
                    if (clr, rng, weight) == ranges[-1] and rc+rows < n: rows += 1
                    rng.colors(clr, n=rows, d=d).swatch(dx, dy, w, h, padding=padding, roundness=roundness)
                    dx += w + padding
                dy += (w+padding) * rows #+ padding
                rc = rows
            x += (w+padding) * cols + padding

        return x, dy

    draw = swatch
    
    def swarm(self, x, y, r=100):
        colors = self.colors(100)
        colors.swarm(x, y, r)



class ColorThemeDB(object):
  def __init__(self, db=DEFAULT_DB):    
    self.path = db
    _mkdir(dirname(db))

    # extract the aggregated themes to app_support if they're not there already
    themes_dir = join(CONFIG_DIR,'themes')
    if not isdir(themes_dir):
      aggregated = ZipFile(join(py_root, 'default.themes'))
      for collection in aggregated.namelist():
        aggregated.extract(collection, CONFIG_DIR)

    # build the db from the aggregated theme data if db is missing
    if not exists(db):
      self.restore(themes_dir)
    else:
      self.synchronize(themes_dir)
      
  #
  # some properties for easy access to catalog information
  # 
  @property
  @contextmanager
  def cursor(self):
    con = sqlite3.connect(self.path)
    con.row_factory = lambda cursor,row:{col[0]:row[idx] for idx, col in enumerate(cursor.description)}
    yield con.cursor()
    con.commit()
    con.close()

  @property
  def collections(self):
    """A list of collection names. Use one as a query argument to focus the search."""
    return self._collections.keys()

  @property
  def _collections(self):
    """A lookup table of collection names to id values"""
    with self.cursor as c:
      return {row['name']:row['id'] for row in c.execute("""SELECT * from collections""")}

  @property
  def colors(self):
    return self._colors.keys()

  @property
  def _colors(self):
    with self.cursor as c:
      return {row['name']:row['id'] for row in c.execute('''SELECT * from words WHERE kind="color"''')}

  @property
  def shades(self):
    return self._shades.keys()
  
  @property
  def _shades(self):
    with self.cursor as c:
      return {row['name']:row['id'] for row in c.execute('''SELECT * from words WHERE kind="shade"''')}

  def queries(self, collection=None):
    """Returns the list of all unique query terms across all collections, or one in particular"""
    with self.cursor as c:
      if not collection:
        # if collection isn't specified, return all unique query terms across all collections
        c.execute("""SELECT DISTINCT name FROM queries""")
        return [row['name'] for row in c.execute("""SELECT DISTINCT name FROM queries""")]
      elif collection in self.collections:
        # otherwise just return the query terms in the specified collection
        collection_id = self._collections[collection]
        return [row['name'] for row in c.execute("""SELECT name FROM queries WHERE collection=?""", [collection_id])]
      else:
        return []

  # 
  # c.r.u.d.
  # 
  def update(self, q, collection, theme):
    if theme is None:
      return self.delete(q, collection)

    with self.cursor as c:
      # find the collection id...
      collection_id = self._collections.get(collection)
      if not collection_id:
        # ...or create a new collection row if none exists
        c.execute('''INSERT INTO collections (name) VALUES (?)''', [collection])
        collection_id = c.lastrowid

      for row in c.execute('''SELECT * FROM queries WHERE name=? AND collection=?''',[q, collection_id]):
        query_id = row['id'] # get a reference to the old query record (if exists)...
        break
      else:
        # ...otherwise create a new query record
        c.execute('''INSERT INTO queries (name, collection) VALUES (?, ?)''', [q, collection_id])
        query_id = c.lastrowid

      # clear out any weights from the old record
      c.execute('''DELETE FROM weights WHERE query=?''',[query_id])

      # write the new theme data to the weights table
      colors, shades = self._colors, self._shades
      weights = []
      for name, color in theme.items():
        weights.append([query_id, colors[name], None, color['weight']])
        for shade, weight in color['shades'].items():
          weights.append([query_id, colors[name], shades[shade], weight])
      c.executemany('''INSERT INTO weights (query, color, shade, weight) VALUES (?,?,?,?)''', weights)
      c.execute('''UPDATE collections SET last=? WHERE id=?''',[int(time.time()), collection_id])


  def query(self, q, collection=None):
    """Retrieve the color palette associated with a query term (optionally filtered to a 
       single collection).

       q is a string present in the list returned by self.queries()
       collection (if present) is a collection name found in self.collections

       returns a (collection-name, colors-dict) tuple containing the name of the collection
       where the query term was found and a nested dictionary with the mixture parameters
       for the color scheme. The scheme's dict structure is of the form:

        {
          "green":{
            "weight": 0.01,
            "shades":{
              "neutral": 0.1,
              "fresh": 0.2,
              "warm": 0.3,
            }
          },
          "blue":{...},
          ...
        }

    """
    with self.cursor as c:
      collections=self._collections

      c.execute("""SELECT * FROM queries WHERE name=?""", [q])
      if collection:
        for query in c.fetchall():
          # prefer a match in the specified collection
          if query['collection'] == collections[collection]: break
        else:
          # not found in preferred collection
          return collection, {}
      else:
        # if collection is None, search in all the cached collections
        query = c.fetchone()
        if not query:
          # didn't find the query string in any of them
          return collection, {}

      found_in = dict(zip(collections.values(), collections.keys()))[query['collection']]
      c.execute("""SELECT color.name AS color, shade.name AS shade, mixture.weight
                   FROM weights AS mixture
                   LEFT JOIN words AS color ON mixture.color = color.id
                   LEFT JOIN words AS shade ON mixture.shade = shade.id
                   WHERE query=? ORDER BY shade ASC, weight DESC""", [query['id']])
      colors = odict()
      for row in c.fetchall():
        clr = colors.get(row['color'], dict(weight=0, shades=odict()))
        if not row['shade']:
          clr['weight'] = row['weight']
        else:
          clr['shades'][row['shade']] = row['weight']
        if row['color'] not in colors:
          colors[row['color']] = clr
      return found_in, colors

  def delete(self, q, collection):
    with self.cursor as c:
      # find the collection id...
      collection_id = self._collections.get(collection)
      if not collection_id:
        return

      for row in c.execute('''SELECT * FROM queries WHERE name=? AND collection=?''',[q, collection_id]):
        query_id = row['id'] # get a reference to the old query record (if exists)...
        break
      else:
        return

      # clear out weights from the old record
      c.execute('''DELETE FROM weights WHERE query=?''',[query_id])

      # delete the query record
      c.execute('''DELETE FROM queries WHERE id=?''',[query_id])

      for row in c.execute('''SELECT * FROM queries WHERE collection=?''',[collection_id]):
        # if any other queries still exist in the collection, update mtime and bail out...
        c.execute('''UPDATE collections SET last=? WHERE id=?''',[int(time.time()), collection_id])
        return 

      # ...otherwise delete the collection
      c.execute('''DELETE FROM collections WHERE id=?''',[collection_id])      
  # 
  # import/export database from/to flat files. can read from either a folder of 
  # collection.json files or a hierarchy of collection/query.xml folders and files.
  # 
  def synchronize(self, themedir):
    """Keep the app_support themes directory in sync with the database"""

    with self.cursor as c:
      last = {row['name']:row['last'] for row in c.execute('''SELECT * FROM collections''')}

    # check for user modifications in ~/Library/Application Support/NodeBox/colors/themes
    seen = []
    for fn in glob(join(themedir, '*.json')):
      mtime = int(os.path.getmtime(fn))
      collection = splitext(basename(fn))[0]
      if mtime>last[collection]:
        self.restore(themedir, collection)
      elif mtime<last[collection]:
        self.dump(themedir, collection)
      seen.append(collection)

    # generate json files for any collection not found in the themedir
    for collection in last:
      if collection in seen: continue
      self.dump(themedir, collection)

  def dump(self, themedir, collection=None):
    _mkdir(themedir)

    with self.cursor as c:
      collections, last = {}, {}
      for collect in c.execute("""SELECT * FROM collections"""):
        collections[collect['name']] = collect['id']
        last[collect['name']] = collect['last']
      if collection:
        collections = {collection:collections[collection]}
      for name in collections:
        queries = dict((q['name'], q['id']) for q in c.execute("""SELECT * FROM queries WHERE collection=?""",[collections[name]]))
        c.execute("""SELECT color.name AS color, 
                            shade.name AS shade, 
                            mixture.weight, 
                            query.collection,
                            query.name AS query
                     FROM weights AS mixture
                     LEFT JOIN queries AS query ON mixture.query = query.id
                     LEFT JOIN words AS color ON mixture.color = color.id
                     LEFT JOIN words AS shade ON mixture.shade = shade.id
                     WHERE collection=? ORDER BY query.name""", [collections[name]])

        output = {}
        for row in c.fetchall():
          colors = output.get(row['query'], {})
          color = colors.get(row['color'], {"weight":None, "shades":{}})
          if row['shade']:
            color['shades'][row['shade']] = row['weight']
          else:
            color['weight'] = row['weight']
          colors[row['color']] = color
          output[row['query']] = colors

        with file(join(themedir, '%s.json'%name), 'w') as f:
          json.dump(output, f, encoding='utf-8', indent=2)
        os.utime(join(themedir, '%s.json'%name), (last[name],last[name]))

  def restore(self, themedir, collection=None):
    json_files = set(glob(join(themedir, '*.json')))
    xml_dirs = set(dirname(p) for p in glob(join(themedir,'*/*.xml')))
    collections = json_files.union(xml_dirs)
    if collection:
      collections = [c for c in collections if splitext(basename(c))[0]==collection]
    if not collections:
      notfound = 'No json files found in %s'%themedir
      if collection:
        notfound = 'Json file not found at %s'%join(themedir, collection+'.json')
      raise Exception(notfound)

    # delete the old db (if this is a full restoration)
    if exists(self.path) and collection is None:
      os.unlink(self.path)

    with self.cursor as c:      
      if collection is None or not exists(self.path):
        # set up tables in the new db file
        print "Aggregating color themes in %s"%self.path.replace(os.getenv('HOME'),'~')
        print "This should be a one-time process when you first access the colors library."
        c.execute('''CREATE TABLE words (id integer PRIMARY KEY AUTOINCREMENT UNIQUE DEFAULT 1, name text, kind text)''')
        for color in sorted(['blue', 'pink', 'purple', 'yellow', 'black', 'cyan', 'orange', 'green', 'white', 'red']):
          c.execute('''INSERT INTO words (name, kind) VALUES (?, ?)''', [color, 'color'])
        for shade in sorted(['light', 'hard', 'weak', 'neutral', 'dark', 'bright', 'warm', 'fresh', 'soft', 'intense', 'cool']):
          c.execute('''INSERT INTO words (name, kind) VALUES (?, ?)''', [shade, 'shade'])
        
        c.execute('''CREATE TABLE collections (id integer PRIMARY KEY AUTOINCREMENT UNIQUE DEFAULT 1, name text, last integer)''')        
        c.execute('''CREATE TABLE queries (id integer PRIMARY KEY AUTOINCREMENT UNIQUE DEFAULT 1, name text, collection integer)''')
        c.execute('''CREATE TABLE weights (id integer PRIMARY KEY AUTOINCREMENT UNIQUE DEFAULT 1, query integer, color integer, shade integer, weight real)''')
      else:
        # if we're only replacing a single collection, just clear out its entries rather
        # than wiping the entire db
        collection_id = self._collections.get(collection)
        if collection_id:
          c.execute("""DELETE FROM weights WHERE id IN (
                              SELECT weights.id FROM weights
                                LEFT JOIN queries AS query ON weights.query = query.id
                                LEFT JOIN collections AS collection ON query.collection = collection.id
                              WHERE query.collection=?)""", [collection_id])
          c.execute("""DELETE FROM queries WHERE collection=?""",[collection_id])


      # make sure there's a collections record for each group we're adding
      group_ids = self._collections
      for fn in collections:
        group = splitext(basename(fn))[0]
        if group not in group_ids:
          c.execute('''INSERT INTO collections (name) VALUES (?)''', [group])
          group_ids[group] = c.lastrowid

      words = dict(colors=self._colors, shades=self._shades)
      for fn in collections:
        group = splitext(basename(fn))[0]
        if fn.endswith('.json'):
          try:
            queries = json.load(file(fn))
          except ValueError as e:
            e.args = ("Error decoding %s"%fn.replace(os.getenv('HOME'),'~'),)+e.args
            raise
          last = os.path.getmtime(fn)
        else:
          # handle the old prism xml format too
          import xml.etree.ElementTree as ET
          queries = {}
          last = None
          for query_fn in glob(join(fn,'*')):
            last = max(last, os.path.getmtime(query_fn))
            tree = ET.parse(query_fn)
            root = tree.getroot()
            colors = {}
            for clr in root.iter('color'):
              color = dict(weight=float(clr.attrib['weight']), shades={})
              name = clr.attrib['name']
              for shd in clr.iter('shade'):
                color['shades'][shd.attrib['name']] = float(shd.attrib['weight'])
              colors[name] = color
            queries[root.attrib['query']] = colors

        if collection is None: # Only be noisy when doing the big batch-install up front
          print " ", (fn if fn.endswith('.json') else fn+'/*xml').replace(os.getenv('HOME'),'~')

        for query, colors in queries.items():
          c.execute('''INSERT INTO queries (name, collection) VALUES (?, ?)''', [query, group_ids[group]])
          query_id = c.lastrowid

          weights = []
          for name, color in colors.items():
            weights.append([query_id, words['colors'][name], None, color['weight']])
            for shade, weight in color['shades'].items():
              weights.append([query_id, words['colors'][name], words['shades'][shade], weight])

          c.executemany('''INSERT INTO weights (query, color, shade, weight) VALUES (?,?,?,?)''', weights)
        c.execute('''UPDATE collections SET last=? WHERE name=?''', [last, group])
