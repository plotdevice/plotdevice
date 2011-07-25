import os
import Image

HTML_HEADER = r'''
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<head>
<meta http-equiv="content-type" content="text/html; charset=utf-8">
<title>Vdiff Test Results</title>
<style type="text/css" media="all">
body { margin: 20px 0 20px 150px; }
body, td, th { font: 11px/1.5em "Lucida Grande", sans-serif; }
h1 { font-size: 160%; padding: 0; margin: 0em 0 -2em 0; }
h2 { font-size: 130%; padding: 0; margin: 4em 0 0.2em 0; clear:both; }
img { float: left; border: 1px solid #000; margin: 2px; }
.different table { background: red; }
table.statistics { margin:2px; width:16em; border:1px solid #666; }
table.statistics td { font-weight: bold; text-align: right; padding: 2px 5px; }
table.statistics td + td { font-weight: normal; text-align: left; }
tr.even { background: #eee; }
tr.odd { background: #ddd; }
</style>
</head>
<body>
<h1>vdiff tests</h1>
'''

HTML_FOOTER = r'''
</body>
</html>
'''

def format_stats(stats):
    if stats.number_of_differences > 0:
        clz = " different"
    else:
        clz = ""

    html  = """<h2>%s</h2>\n""" % stats.name
    html += """<div class="stats%s">""" % clz
    html += """<a href="%s" target="_blank"><img src="%s" width="150" height="150"></a>\n""" % (stats.fname1, stats.fname1)
    html += """<a href="%s" target="_blank"><img src="%s" width="150" height="150"></a>\n""" % (stats.fname2, stats.fname2)
    if stats.comparison_image_fname is not None:
        html += """<a href="%s" target="_blank"><img class="compare" src="%s" width="150" height="150"></a>\n""" % (stats.comparison_image_fname, stats.comparison_image_fname)
    html += """<table class="statistics" height="152">\n"""
    html += """<tr class="odd"><td>Differences:</td><td>%i</td></tr>\n""" % len(stats.differences)
    html += """<tr class="even"><td>Total delta:</td><td>%i</td></tr>\n""" % stats.total_delta
    html += """<tr class="odd"><td>Max delta:</td><td>%i</td></tr>\n""" % stats.max_delta
    html += """<tr class="even"><td>Mean:</td><td>%.4f</td></tr>\n""" % stats.mean
    html += """<tr class="odd"><td>Stdev:</td><td>%.4f</td></tr>\n""" % stats.stdev
    html += """</table>\n"""
    html += """</div>"""
    return html
    
def format_stats_list(stats_list):
    html = HTML_HEADER
    for stats in stats_list:
        html += format_stats(stats)
    html += HTML_FOOTER
    return html

def compare_pixel(px1, px2):
    if px1 == px2:
        return 0
    r1, g1, b1, a1 = px1
    r2, g2, b2, a2 = px2
    return abs(r1-r2) + abs(g1-g2) + abs(b1-b2) + abs(a1-a2)

def visual_diff(img1, img2, threshold=0, stop_on_diff=False):
    if isinstance(img1, str) or isinstance(img1, unicode):
        img1 = Image.open(img1)
        img1 = img1.convert("RGBA")
    if isinstance(img2, str) or isinstance(img2, unicode):
        img2 = Image.open(img2)
        img2 = img2.convert("RGBA")
    assert img1.size == img2.size
    w, h = img1.size
    data1 = img1.getdata()
    data2 = img2.getdata()
    size = len(data1)
    differences = []
    for i in xrange(size):
        delta = compare_pixel(data1[i], data2[i])
        if delta > threshold:
            x = i % w
            y = i / w
            differences.append( ( (x, y), data1[i], data2[i], delta ) )
            if stop_on_diff:
                # print data1[i], data2[i]
                break
    return differences
    
def make_comparison_image(size, differences):
    img = Image.new("L", size, color=255)
    for pos, d1, d2, delta in differences:
        img.putpixel(pos, 255-delta)
    return img

def isEqual(fname1, fname2, threshold=0):
    diff = visual_diff(fname1, fname2, threshold, stop_on_diff=True)
    if len(diff) == 0:
        return True
    return False
    
class Statistics(object):
    def __init__(self, fname1, fname2, differences=None, name=""):
        self.fname1 = fname1
        self.fname2 = fname2
        if differences is None:
            differences = visual_diff(fname1, fname2)
        self.differences = differences
        self.name = name

        img1 = Image.open(fname1)
        self.width, self.height = img1.size
        
        self._comparison_image = None
        self.comparison_image_fname = None
        self.calculate()
        
    def calculate(self):
        diff = self.differences

        total_delta = 0
        max_delta = 0
        for pos, d1, d2, delta in diff:
            total_delta += delta
            max_delta = max(max_delta, delta)
        self.total_delta = total_delta
        self.max_delta = max_delta
        self.mean = mean = total_delta / float(self.width * self.height)

        stdev = 0
        for pos, d1, d2, delta in diff:
            stdev += pow(delta-mean, 2)
        stdev /= float(self.width * self.height)
        self.stdev = stdev

    def _get_size(self):
        return self.width, self.height
    size = property(_get_size)
    
    def _get_number_of_differences(self):
        return len(self.differences)
    number_of_differences = property(_get_number_of_differences)
    
    def _get_comparison_image(self):
        if self._comparison_image is None:
            self._comparison_image = make_comparison_image(self.size, self.differences)
        return self._comparison_image
    comparison_image = property(_get_comparison_image)
    
    def save_comparison_image(self, fname):
        self.comparison_image.save(fname)
        self.comparison_image_fname = fname
    
    def __str__(self):
        return "<Statistics diff:%s total_delta:%s max_delta:%s mean:%.4f stdev:%.4f>" % (
            len(self.differences), self.total_delta, self.max_delta, self.mean, self.stdev)

def statistics(fname1, fname2, threshold=0):    
    diff = visual_diff(fname1, fname2)    
    stats = Statistics(fname1, fname2, diff)

    print "Differences:", len(stats.differences)
    print "Total delta:", stats.total_delta
    print "Max delta:", stats.max_delta
    print "Mean:", stats.mean
    print "Stdev:", stats.stdev

    stats.comparison_image.save('cmp.png')
    
def test_vdiff(self):
    #fname1 = 'vdiff-tests/001-added-square/original.png'
    #fname2 = 'vdiff-tests/001-added-square/bluesquare.png'

    #fname1 = 'vdiff-tests/002-antialiased-text/preview.png'
    #fname2 = 'vdiff-tests/002-antialiased-text/photoshop.png'

    #fname1 = 'vdiff-tests/003-movement/original.png'
    #fname2 = 'vdiff-tests/003-movement/moved.png'

    #fname1 = 'vdiff-tests/004-color/original.png'
    #fname2 = 'vdiff-tests/004-color/darker.png'

    #fname1 = 'vdiff-tests/005-antialiased-text/none.png'
    #fname2 = 'vdiff-tests/005-antialiased-text/smooth.png'

    #fname1 = 'vdiff-tests/006-totally-different/ant.png'
    #fname2 = 'vdiff-tests/006-totally-different/people.png'

    fname1 = 'vdiff-tests/007-black-white/black.png'
    fname2 = 'vdiff-tests/007-black-white/white.png'
    
    statistics(fname1, fname2)
    
def usage():
    print """vdiff -- visually compare images
Usage: vdiff <image1> <image2> [threshold]"""

if __name__=='__main__':
    import sys
    if len(sys.argv) < 3:
        usage()
    else:
        fname1 = sys.argv[1]
        fname2 = sys.argv[2]
        try:
            threshold = int(sys.argv[3])
        except:
            threshold = 0
        statistics(fname1, fname2, threshold)