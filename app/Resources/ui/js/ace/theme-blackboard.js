define("ace/theme/blackboard",["require","exports","module","ace/lib/dom"], function(require, exports, module) {

exports.isDark = true;
exports.cssClass = "ace-blackboard";
exports.cssText = "\
.ace-blackboard .ace_gutter {\
background: #0c1021;\
color: #AEAEAE;\
}\
.ace-blackboard .ace_print-margin {\
width: 1px;\
background: #e8e8e8;\
}\
.ace-blackboard {\
background-color: #0C1021;\
color: #F8F8F8;\
}\
.ace-blackboard .ace_cursor {\
color: rgba(255, 255, 255, 0.65);\
}\
.ace-blackboard .ace_marker-layer .ace_selection {\
background: #325087;\
}\
.ace-blackboard.ace_multiselect .ace_selection.ace_start {\
box-shadow: 0 0 3px 0px #0C1021;\
border-radius: 2px;\
}\
.ace-blackboard .ace_marker-layer .ace_step {\
background: rgb(198, 219, 174);\
}\
.ace-blackboard .ace_marker-layer .ace_bracket {\
margin: -1px 0 0 -1px;\
border: 1px solid rgba(255, 255, 255, 0.25);\
}\
.ace-blackboard .ace_marker-layer .ace_active-line {\
background: rgba(255, 255, 255, 0.059);\
}\
.ace-blackboard .ace_gutter-active-line {\
background-color: rgba(255, 255, 255, 0.059);\
}\
.ace-blackboard .ace_marker-layer .ace_selected-word {\
border: 1px solid #253B76;\
}\
.ace-blackboard .ace_fold {\
background-color: #FBDE2D;\
border-color: #F8F8F8;\
}\
.ace-blackboard .ace_keyword,\
.ace-blackboard .ace_storage {\
color: #FBDE2D;\
}\
.ace-blackboard .ace_constant {\
color: #D8FA3C;\
}\
.ace-blackboard .ace_support {\
color: #8DA6CE;\
}\
.ace-blackboard .ace_invalid.ace_illegal {\
color: #F8F8F8;\
background-color: #9D1E15;\
}\
.ace-blackboard .ace_invalid.ace_deprecated {\
font-style: italic;\
color: #AB2A1D;\
}\
.ace-blackboard .ace_string {\
color: #61CE3C;\
}\
.ace-blackboard .ace_invisible{\
color:rgba(174, 174, 174, 0.5);\
}\
.ace-blackboard .ace_comment {\
color: #AEAEAE;\
}\
.ace-blackboard .ace_meta.ace_tag {\
color: #7F90AA;\
}\
.ace-blackboard .ace_variable,\
.ace-blackboard .ace_variable.ace_language {\
color:rgba(255, 100, 0, 1.0);\
}";

var dom = require("../lib/dom");
dom.importCssString(exports.cssText, exports.cssClass);
});                (function() {
                    window.require(["ace/theme/blackboard"], function(m) {
                        if (typeof module == "object" && typeof exports == "object" && module) {
                            module.exports = m;
                        }
                    });
                })();
            