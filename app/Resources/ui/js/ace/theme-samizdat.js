define("ace/theme/samizdat-css",["require","exports","module"], function(require, exports, module){module.exports = `
.ace-samizdat .ace_gutter {
  background: #090B10;
  color: #858585
}

.ace-samizdat .ace_print-margin {
  width: 1px;
  background: #181920
}

.ace-samizdat {
  background-color: #090B10;
  color: #EBDBB2
}

.ace-samizdat .ace_cursor {
  color: #D4D4D4
}

.ace-samizdat .ace_marker-layer .ace_selection {
  background: #569CD655
}

.ace-samizdat.ace_multiselect .ace_selection.ace_start {
  box-shadow: 0 0 3px 0px #090B10;
}

.ace-samizdat .ace_marker-layer .ace_step {
  background: rgb(89, 66, 0)
}

.ace-samizdat .ace_marker-layer .ace_bracket {
  margin: -1px 0 0 -1px;
  border: 1px solid #FFFFFF44
}

.ace-samizdat .ace_marker-layer .ace_active-line {
  background: #2A2A2A
}

.ace-samizdat .ace_gutter-active-line {
  background-color: #2A2A2A
}

.ace-samizdat .ace_marker-layer .ace_selected-word {
  border: 1px solid #303030
}

.ace-samizdat .ace_invisible {
  color: #6C6C6C
}

.ace-samizdat .ace_entity.ace_name.ace_tag,
.ace-samizdat .ace_keyword,
.ace-samizdat .ace_meta.ace_tag,
.ace-samizdat .ace_storage {
  color: #FB5245;
  font-style: italic
}

.ace-samizdat .ace_keyword.ace_operator {
  color: #D4D4D4;
  font-style: normal
}

.ace-samizdat .ace_punctuation,
.ace-samizdat .ace_punctuation.ace_tag {
  color: #EBDBB2
}

.ace-samizdat .ace_constant.ace_character,
.ace-samizdat .ace_constant.ace_language,
.ace-samizdat .ace_constant.ace_numeric,
.ace-samizdat .ace_constant.ace_other {
  color: #569CD6
}

.ace-samizdat .ace_constant.ace_character.ace_escape,
.ace-samizdat .ace_constant.ace_language.ace_escape {
  color: #D7BA7D
}

.ace-samizdat .ace_invalid {
  color: #EBDBB2;
  background-color: #F44747
}

.ace-samizdat .ace_invalid.ace_deprecated {
  color: #EBDBB2;
  background-color: #FFB300
}

.ace-samizdat .ace_entity.ace_name.ace_function,
.ace-samizdat .ace_support.ace_function {
  color: #FAC149
}

.ace-samizdat .ace_fold {
  background-color: #B2CCD6;
  border-color: #EBDBB2
}

.ace-samizdat .ace_storage.ace_type,
.ace-samizdat .ace_support.ace_class,
.ace-samizdat .ace_support.ace_type {
  font-style: italic;
  color: #B2CCD6
}

.ace-samizdat .ace_entity.ace_other.ace_attribute-name {
  font-style: italic;
  color: #B2CCD6
}

.ace-samizdat .ace_entity.ace_other,
.ace-samizdat .ace_variable {
  color: #EBDBB2
}

.ace-samizdat .ace_variable.ace_parameter {
  font-style: italic;
  color: #B2CCD6
}

.ace-samizdat .ace_string {
  color: #B8BB26
}

.ace-samizdat .ace_string.ace_regexp {
  color: #F44747
}

.ace-samizdat .ace_comment {
  color: #A89984;
  font-style: italic
}

.ace-samizdat .ace_indent-guide {
  background: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAACCAYAAACZgbYnAAAAEElEQVR42mP4//+/AgOIAAAhyQY7mIrdGgAAAABJRU5ErkJggg==) right repeat-y
}

.ace-samizdat .ace_indent-guide-active {
  background: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAACCAYAAACZgbYnAAAAEElEQVR42mPYdOZaJAOIAAAbzQVbMToY0QAAAABJRU5ErkJggg==) right repeat-y;
}
`;

});

define("ace/theme/samizdat",["require","exports","module","ace/theme/samizdat-css","ace/lib/dom"], function(require, exports, module){exports.isDark = true;
exports.cssClass = "ace-samizdat";
exports.cssText = require("./samizdat-css");
var dom = require("../lib/dom");
dom.importCssString(exports.cssText, exports.cssClass, false);

});                (function() {
                    window.require(["ace/theme/samizdat"], function(m) {
                        if (typeof module == "object" && typeof exports == "object" && module) {
                            module.exports = m;
                        }
                    });
                })();
