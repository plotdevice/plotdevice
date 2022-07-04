// the language-tools extension provides snippets and autocomplete
ace.require("ace/ext/language_tools");

// Wrap the ace UndoManager's mutation methods with callbacks to the pyobjc EditorView
// keeping it up-to-date on whether the file has been modified & whether undo/redo are available
const {UndoManager:__UndoManager} = ace.require('ace/undomanager')
function UndoManager(){ __UndoManager.call(this) }
UndoManager.prototype = Object.create(__UndoManager.prototype);
for (const method of ['add', 'undo', 'redo', 'reset']){
    UndoManager.prototype[method] = function(){
        __UndoManager.prototype[method].call(this, ...arguments);
        app.edits_(this.$undoStack.length)
    }
}

var Editor = function(elt){
    var dom = document.querySelector(elt)
    var ed = ace.edit(dom.getAttribute('id'))
    var undo = new UndoManager()
    var sess = null
    var _menu_cmds = { // commands whose keyboard shortcuts are caught by ace rather than NSView
        "Edit":['selectline', 'splitIntoLines', 'addCursorAbove', 'addCursorBelow', 'centerselection',
                'blockindent', 'blockoutdent', 'togglecomment','selectMoreAfter', 'selectMoreBefore',
                'expandSnippet', 'startAutocomplete', 'movelinesup', 'movelinesdown','modifyNumberUp',
                'modifyNumberDown'],
        "Python":[]
    }
    var _htimer = null, _vtimer = null, _hmin=0, _vmin=0;
    var that = {
        init:function(){

            // configure the editor
            ed.setShowPrintMargin(false);
            ed.setFadeFoldWidgets(true);
            ed.setHighlightActiveLine(false);
            ed.setHighlightGutterLine(false);
            console.log('COMMANDS', ed.commands)
            ed.commands.addCommands(PLOTDEVICE_KEYBINDINGS)
            ed.setOptions({
                enableBasicAutocompletion: true,
                // enableLiveAutocompletion: true,
                enableSnippets: true
            });
            ed.renderer.updateCharacterSize()
            ed.commands.on("afterExec", that._commandStream)
            ed.on("blur", that._blur)
            ed.on("focus", that._focus)

            // configure the buffer
            sess = ed.getSession()
            sess.setMode("ace/mode/plotdevice");
            sess.setTabSize(4);
            sess.setUseSoftTabs(true);
            sess.setUndoManager(undo);

            // it would be nice if this didn't *select* the undo segment, but did *scroll*
            // the viewport to the cursor position. ace.js's default behavior is all or none
            // sess.setUndoSelect(false);

            // being able to switch between light and dark scrollbars also means being
            // responsible for their hide/show behavior, sadly....
            sess.on("changeScrollLeft", that._scroll_h)
            sess.on("changeScrollTop", that._scroll_v)
            that.ready = true // flag that the objc side can start sending messages
            return that
        },
        _commandStream:function(e){
            // listen for commands that have key equivalents in the main menu and notify the
            // objc side of things when one of them is entered
            var cmd = e.command.name
            for (const [cmds, menu] of Object.entries(_menu_cmds)){
                if (cmds.includes(cmd)) app.flash_(menu)
            }
        },
        _scroll_h:function(x){
            var now = Date.now()
            if (_htimer) clearTimeout(_htimer)
            else{
                _hmin = now + 500
                dom.classList.add('scrolling-h')
            }
            _htimer = setTimeout(function(){
                dom.classList.remove('scrolling-h')
                _htimer=null
            }, Math.max(_hmin-now, 180))
        },
        _scroll_v:function(y){
            var now = Date.now()
            if (_vtimer) clearTimeout(_vtimer)
            else{
                _vmin = now + 500
                dom.classList.add('scrolling-v')
            }
            _vtimer = setTimeout(function(){
                dom.classList.remove('scrolling-v')
                _vtimer=null
            }, Math.max(_vmin-now, 180))
        },


        blur:function(){
            ed.blur()
        },
        _blur:function(){
            ed.setHighlightActiveLine(false)
            ed.setHighlightGutterLine(false)
        },

        focus:function(){
            ed.focus()
        },
        _focus:function(){
            ed.setHighlightActiveLine(true)
            ed.setHighlightGutterLine(true)
        },

        source:function(src){
            if (src===undefined){
                return ed.getValue()
            }else{
                ed.execCommand("refreshdoc",src) // set src without adding undo action
                ed.clearSelection();
                ed.moveCursorTo(0, 0);
            }
        },
        font:function(family, px){
            dom.style.fontFamily = family
            dom.style.fontSize = px
        },
        theme:function(thm){
            if (thm===undefined){
                return ed.getTheme()
            }else{
                ed.setTheme(thm)
            }
        },
        bindings:function(mode){
            if (mode===undefined){
                return ed.getKeyboardHandler()
            }else{
                module = (mode=='mac') ? null : 'ace/keyboard/'+mode
                ed.setKeyboardHandler(module)
            }
        },
        selected:function(){
            var sel = ed.getSelection()
            var rng = ed.getSelectionRange()
            var tok = sess.getTokens(rng.start.row)
            console.log('tokens', tok.map(t => t.type))
            var at = sess.getTokenAt(rng.start.row,rng.start.column)

            tok.forEach((t, i) => {
                if (t===at) console.log('FOUND', t,'at',i)
            })
            var word_rng = sess.getAWordRange(rng.start.row,rng.start.column)
            var word = sess.getTextRange(word_rng)
            return word
        },
        exec:function(cmd){
            ed.execCommand(cmd)
        },
        wrap:function(mode){
            if (mode===undefined){
                return sess.getUseWrapMode();
            }else{
                sess.setUseWrapMode(mode);
            }
        },
        invisibles:function(mode){
            if (mode===undefined){
                return sess.getShowInvisibles();
            }else{
                ed.setShowInvisibles(mode);
            }
        },
        undo:function(){
            undo.undo()
        },
        redo:function(){
            undo.redo()
        },
        jump:function(line){
            ed.gotoLine(line);
        },
        insert:function(txt){
            ed.insert(txt)
        },
        mark:function(err, lines){
            if (err==null){
                sess.clearAnnotations()
            }else{
                var anns = lines.map((line, i) => {
                    var ann = {row:line, col:0, type:"warning"}
                    if (i==0) Object.assign(ann, {type:"error", text:err})
                    return ann
                })
                sess.setAnnotations(anns)
            }

        }
    }


    return dom ? that.init() : {}
}
