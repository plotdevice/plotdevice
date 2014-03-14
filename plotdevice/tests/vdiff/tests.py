import os, glob
from plotdevice.util import vdiff

TEST_PATH = 'images'
create_compare_image = True

def format_stats(name, stats, compare_image=None):
    html  = """<h2>%s</h1>\n""" % name
    html += """<img src="%s" width="150" height="150">\n""" % stats.fname1
    html += """<img src="%s" width="150" height="150">\n""" % stats.fname2
    if compare_image is not None:
        html += """<img class="compare" src="%s" width="150" height="150">\n""" % compare_image
    html += """<table class="statistics">\n"""
    html += """<tr class="odd"><td>Differences:</td><td>%i</td></tr>\n""" % len(stats.differences)
    html += """<tr class="even"><td>Total delta:</td><td>%i</td></tr>\n""" % stats.total_delta
    html += """<tr class="odd"><td>Max delta:</td><td>%i</td></tr>\n""" % stats.max_delta
    html += """<tr class="even"><td>Mean:</td><td>%.4f</td></tr>\n""" % stats.mean
    html += """<tr class="odd"><td>Stdev:</td><td>%.4f</td></tr>\n""" % stats.stdev
    html += """</table>\n"""
    return html

html = """<html>
<head>
<meta http-equiv="content-type" content="text/html; charset=utf-8">
<title>vdiff tests</title>
<link rel="stylesheet" type="text/css" href="images/vdiff.css" media="all">
</head>
<body>
<h1>vdiff tests</h1>
"""

for testPath in glob.glob('%s/*' % TEST_PATH):
    if not os.path.isdir(testPath): continue
    name = os.path.basename(testPath)
    print name
    testFiles = glob.glob('%s/*.png' % testPath)
    try:
        testFiles.remove('%s/_compare.png' % testPath)
    except ValueError: pass
    if len(testFiles) == 2:
        fname1, fname2 = testFiles
        stats = vdiff.Statistics(fname1, fname2)
        if create_compare_image:
            compare_image = vdiff.make_comparison_image(stats.size, stats.differences)
            compare_image_fname = '%s/_compare.png' % testPath
            compare_image.save(compare_image_fname)
            html += format_stats(name, stats, compare_image_fname)
        else:
            html += format_stats(name, stats)
    else:
        print "path %s has more than two PNG images: %s" % (testPath, testFiles)

html += """</body>\n</html>\n"""
    
fp = open('test-results.html', 'w')
fp.write(html)
fp.close()

print "Generated test-results.html"