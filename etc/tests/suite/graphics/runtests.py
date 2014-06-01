import shutil
import os
import re
from glob import glob

import sys
sys.path.insert(0, '../..')

from plotdevice.console import make_image
from plotdevice.util import vdiff

test_re = re.compile("^[0-9]{3}.*.py$")

class CompareError(Exception):
    def __init__(self, scriptname, stats):
        self.scriptname = scriptname
        self.stats = stats
    def __str__(self):
        return "%s: Images don't match: %s" % (self.scriptname, self.stats)
    
all_python_files = glob("*.py")
test_files = [file for file in all_python_files if test_re.match(file)]

# Remove and re-create the results directory
try:
    shutil.rmtree("_results")
except OSError, e:
    if e.errno != 2: # The directory doesn't exist yet
        raise e
RESULTS_DIR = "_results"
os.mkdir("_results")

stats_list = []
differences = False
# Test all the scripts one by one.
for test_file in test_files:
    basename = os.path.splitext(test_file)[0]
    ref_image = "%s.png" % basename
    result_image = os.path.join(RESULTS_DIR, "%s.result.png" % basename)
    test_script = open(test_file).read()
    make_image(test_script, result_image)
    
    stats = vdiff.Statistics(ref_image, result_image, name=basename)
    stats.save_comparison_image(os.path.join(RESULTS_DIR, "%s.compare.png" % basename))
    stats.fname1 = "../" + stats.fname1 # This will link to the original file
    stats.fname2 = os.path.split(stats.fname2)[1] # This will link to a file in the same folder
    stats.comparison_image_fname = os.path.split(stats.comparison_image_fname)[1] # This will link to a file in the same folder
    stats_list.append(stats)
    
    if stats.number_of_differences > 0:
        differences = True
        print "E",
    else:
        print ".",
print

html = vdiff.format_stats_list(stats_list)
open(os.path.join(RESULTS_DIR, '_results.html'), 'w').write(html)

if differences:
    for stats in stats_list:
        if stats.number_of_differences > 0:
            print "%s: Images don't match." % stats.name