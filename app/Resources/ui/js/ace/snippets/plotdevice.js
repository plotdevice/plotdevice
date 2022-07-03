define("ace/snippets/plotdevice",["require","exports","module"], function(require, exports, module) {
"use strict";

exports.snippetText = "### general purpose\n\
\n\
snippet {\n\
	{\"${1:k}\":${2:v}, kw$3}\n\
snippet kw\n\
	\"${1:k}\":${2:v}, kw$3\n\
snippet dict\n\
	dict(${1:k}=${2:v}, dkw$3)\n\
snippet dkw\n\
	${1:k}=${2:v}, dkw$3\n\
snippet t\n\
	True\n\
snippet f\n\
	False\n\
snippet lorem\n\
	lorem = \"Lorem ipsum dolor sit amet, consectetur adipisicing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum.\"\n\
snippet draw\n\
	def draw(state):\n\
	    print(FRAME$1)\n\
snippet setup\n\
	def setup(state):\n\
	    $1\n\
snippet stop\n\
	def stop(state):\n\
	    $1\n\
snippet anim\n\
	speed(${1:30})$2\n\
	def setup(state):\n\
	    pass\n\
	def draw(state):\n\
	    print(FRAME)\n\
	def stop(state):\n\
	    pass\n\
\n\
\n\
### Some handy abbreviations borrowed from python.snippets\n\
\n\
snippet #!\n\
	#!/usr/bin/env python3 -m plotdevice\n\
snippet imp\n\
	import ${1:module}\n\
snippet from\n\
	from ${1:package} import ${2:module}\n\
snippet wh\n\
	while ${1:condition}:\n\
	  ${2:# TODO: write code...}\n\
snippet with\n\
	with ${1:expr} as ${2:var}:\n\
	  ${3:# TODO: write code...}\n\
# New Class\n\
snippet cl\n\
	class ${1:ClassName}(${2:object}):\n\
	  \"\"\"${3:docstring for $1}\"\"\"\n\
	  def __init__(self, ${4:arg}):\n\
	    ${5:super($1, self).__init__()}\n\
	    self.$4 = $4\n\
	    ${6}\n\
# New Function\n\
snippet def\n\
	def ${1:fname}($2):\n\
	    ${3}\n\
# New Method\n\
snippet defs\n\
	def ${1:mname}(self, ${2:arg}):\n\
	  ${3}\n\
# self\n\
snippet .\n\
	self.\n\
# Ifs\n\
snippet if\n\
	if ${1:condition}:\n\
	  ${2}\n\
snippet el\n\
	else:\n\
	  ${1}\n\
snippet ei\n\
	elif ${1:condition}:\n\
	  ${2}\n\
# For\n\
snippet for\n\
	for ${1:item} in ${2:items}:\n\
	  ${3}\n\
# Lambda\n\
snippet ld\n\
	${1:var} = lambda ${2:vars} : ${3:action}\n\
snippet try\n\
	try:\n\
	  ${1:# TODO: write code...}\n\
	except ${2:Exception} as ${3:e}:\n\
	  ${4:raise $3}\n\
snippet ifmain\n\
	if __name__ == '__main__':\n\
	  ${1:main()}\n\
# __dunder__\n\
snippet _\n\
	__${1:init}__${2}\n\
snippet pprint\n\
	import pprint; pprint.pprint(${1})${2}\n\
# Encodes\n\
snippet cutf8\n\
	# -*- coding: utf-8 -*-\n\
\n\
\n\
### signatures for the plotdevice api\n\
\n\
snippet align\n\
	align(${1:LEFT/RIGHT/CENTER/JUSTIFY})\n\
snippet alpha\n\
	alpha(${1:1.0})\n\
snippet arc\n\
	arc(${1:x}, ${2:y}, ${3:radius}${4:, range=${5:None}, ccw=${6:False}, close=${7:False}})\n\
snippet arcto\n\
	arcto(${1:x}, ${2:y}${3:, cx=${4:None}, cy=${5:None}, radius=${6:None}, ccw=${7:False}, close=${8:False}})\n\
snippet arrow\n\
	arrow(${1:x}, ${2:y}${3:, width=${4:100}, type=${5:NORMAL/FORTYFIVE}, plot=${6:True}})\n\
snippet autoclosepath\n\
	autoclosepath(${1:close=${2:True}})\n\
snippet autotext\n\
	autotext(${1:sourceFile})\n\
snippet background\n\
	background()\n\
snippet beginclip\n\
	beginclip(${1:stencil}${2:, mask=${3:False}, channel=${4:None}})\n\
snippet beginpath\n\
	beginpath(${1:${2:x}, ${3:y}})\n\
snippet bezier\n\
	bezier(${1:${2:x}, ${3:y}}, close=${4:True}, plot=${5:True})\n\
snippet blend\n\
	blend(\"${1:normal}\")\n\
snippet capstyle\n\
	capstyle(${1:style=${2:BUTT/ROUND/SQUARE}})\n\
snippet choice\n\
	choice(${1:seq})\n\
snippet clear\n\
	clear(${1:all})\n\
snippet clip\n\
	clip(${1:stencil}${2:, channel=\"${3:black/white/alpha/red/green/blue}\"})\n\
snippet mask\n\
	mask(${1:stencil}${2:, channel=\"${3:black/white/alpha/red/green/blue}\"})\n\
snippet closepath\n\
	closepath()\n\
snippet color\n\
	color(\"${1:black}\")\n\
snippet colormode\n\
	colormode(${1:mode=${2:RGB/HSB/CMYK}, range=${3:None}})\n\
snippet colorrange\n\
	colorrange(${1:maxval})\n\
snippet curveto\n\
	curveto(${1:x1}, ${2:y1}, ${3:x2}, ${4:y2}, ${5:x}, ${6:y}${7:, close=${8:False}})\n\
snippet drawpath\n\
	drawpath(${1:path})\n\
snippet ellipse\n\
	ellipse(${1:x}, ${2:y}, ${3:width}, ${4:height}${5:, range=${6:None}, ccw=${7:False}, close=${8:False}, plot=${9:True}})\n\
snippet endclip\n\
	endclip()\n\
snippet endpath\n\
	endpath(${1:plot=${2:True}})\n\
snippet export\n\
	export(\"${1:${2:document}.${3:mov}}\"${4:, fps=${5:None}, loop=${6:None}, bitrate=${7:1.0}})\n\
snippet files\n\
	files(\"${1:${2:*}.${3:json}}\", case=${4:True}})\n\
snippet fill\n\
	fill(${1:\"#${2:000}\"})\n\
snippet findpath\n\
	findpath(${1:points}${2:, curvature=${3:1.0}})\n\
snippet findvar\n\
	findvar(${1:name})\n\
snippet font\n\
	font(\"${1:HelveticaNeue-Medium}\", ${2:12}})\n\
snippet fonts\n\
	fonts(${1:like=\"${2:akzidenz}\", western=${3:True}})\n\
snippet fontsize\n\
	fontsize(${1:12})\n\
snippet geometry\n\
	geometry(${1:DEGREES/RADIANS/PERCENT})\n\
snippet grid\n\
	grid(${1:cols}, ${2:rows}${3:, colSize=${4:1}, rowSize=${5:1}, shuffled=${6:False}})\n\
snippet image\n\
	image(\"${1:image.png}\", ${2:x}, ${3:y}${4:, width=${5:None}, height=${6:None}, plot=${7:True}})\n\
snippet imagesize\n\
	imagesize(\"${1:image.png}\"${2:, data=${3:None}})\n\
snippet joinstyle\n\
	joinstyle(${1:MITER/ROUND/BEVEL})\n\
snippet line\n\
	line(${1:x1}, ${2:y1}, ${3:x2}, ${4:y2}${5:, plot=${6:True}})\n\
snippet lineheight\n\
	lineheight(${1:None})\n\
snippet lineto\n\
	lineto(${1:x}, ${2:y}${3:, close=${4:False}})\n\
snippet measure\n\
	measure(${1:obj})\n\
snippet moveto\n\
	moveto(${1:x}, ${2:y})\n\
snippet nofill\n\
	nofill()\n\
snippet nostroke\n\
	nostroke()\n\
snippet noshadow\n\
	noshadow()\n\
snippet ordered\n\
	ordered(${1:seq})\n\
snippet outputmode\n\
	outputmode(${1:RGB/CMYK})\n\
snippet oval\n\
	oval(${1:x}, ${2:y}, ${3:width}, ${4:height}${5:, range=${6:None}, ccw=${7:False}, close=${8:False}, plot=${9:True}})\n\
snippet pen\n\
	pen(${1:nib})\n\
snippet plot\n\
	plot(${1:obj})\n\
snippet poly\n\
	poly(${1:x}, ${2:y}, ${3:radius}, ${4:sides=4}${5:, plot=${6:True}})\n\
snippet pop\n\
	pop()\n\
snippet push\n\
	push()\n\
snippet random\n\
	random(${1:v1=${2:None}, v2=${3:None}})\n\
snippet read\n\
	read(${1:pth}${2:, format=${3:None}, encoding=${4:utf-8}, cols=${5:None}})\n\
snippet rect\n\
	rect(${1:x}, ${2:y}, ${3:width}, ${4:height}${5:, roundness=${6:0.0}, plot=${7:True}})\n\
snippet reset\n\
	reset()\n\
snippet rotate\n\
	rotate(${1:theta})\n\
snippet scale\n\
	scale(${1:x=${2:1}, y=${3:None}})\n\
snippet shadow\n\
	shadow(${1:\"black\"}, blur=${2:10}, offset=${3:10})))\n\
snippet shuffled\n\
	shuffled(${2:seq})\n\
snippet size\n\
	size(${1:width}, ${2:height}, unit=${4:px}})\n\
snippet skew\n\
	skew(${1:horizontal}, ${2:vertical})\n\
snippet speed\n\
	speed(${1:fps})\n\
snippet star\n\
	star(${1:x}, ${2:y}${3:, points=${4:20}, outer=${5:100}, inner=${6:None}, plot=${7:True}}})\n\
snippet stroke\n\
	stroke()\n\
snippet strokewidth\n\
	strokewidth(${1:width})\n\
snippet text\n\
	text(\"${1:txt}\", ${2:x}, ${3:y}${4:, width=${5:None}, height=${6:None}, outline=${7:False}, plot=${8:True}})\n\
snippet textheight\n\
	textheight(\"${1:txt}\"${2:, width=${3:None}})\n\
snippet textmetrics\n\
	textmetrics(\"${1:txt}\"${2:, width=${3:None}, height=${4:None}})\n\
snippet textpath\n\
	textpath(\"${1:txt}\", ${2:x}, ${3:y}${4:, width=${5:None}, height=${6:None}})\n\
snippet textwidth\n\
	textwidth(\"${1:txt}\"${2:, width=${3:None}})\n\
snippet transform\n\
	transform()\n\
snippet transform()\n\
	with transform(${1:${2:CENTER/CORNER, }${3:...}}):\n\
	  $4\n\
snippet translate\n\
	translate(${1:x}, ${2:y})\n\
snippet ximport\n\
	${1:libName} = ximport(\"$1\")\n\
";
exports.scope = "plotdevice";

});                (function() {
                    window.require(["ace/snippets/plotdevice"], function(m) {
                        if (typeof module == "object" && typeof exports == "object" && module) {
                            module.exports = m;
                        }
                    });
                })();
            