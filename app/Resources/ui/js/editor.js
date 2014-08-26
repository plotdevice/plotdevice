// A trivial reimplementation of the default ace undo manager. its only distinction
// is informing the objc EditorView object of edits (via relaying the changeCount int)
var UndoMgr = function() { this.reset(); };
(function() {
     // Provides a means for implementing your own undo manager. `options` has one property, `args`, an [[Array `Array`]], with two elements:
     // - `args[0]` is an array of deltas
     // - `args[1]` is the document to associate with
     // @param {Object} options Contains additional properties
     this.execute = function(options) {
        var deltas = options.args[0];
        this.$doc  = options.args[1]; // the edit session

        if (options.merge && this.hasUndo()){
            this.changeCount--;
            deltas = this.$undoStack.pop().concat(deltas);
        }
        this.$undoStack.push(deltas);
        this.$redoStack = [];

        // The user has made a change after undoing past the last clean state.
        // We can never get back to a clean state now until markClean() is called.
        if (this.changeCount < 0) this.changeCount = NaN;

        this.changeCount++;
        app.edits(this.changeCount)
    };

     // [Perform an undo operation on the document, reverting the last change.]{: #UndoManager.undo}
     // @param {Boolean} dontSelect {:dontSelect}
     // @Returns {Range} The range of the undo.
     this.undo = function(dontSelect) {
        var deltas = this.$undoStack.pop();
        var undoSelectionRange = null;
        if (deltas) {
            undoSelectionRange =
                this.$doc.undoChanges(deltas, dontSelect);
            this.$redoStack.push(deltas);
            this.changeCount--;
            app.edits(this.changeCount)
        }

        return undoSelectionRange;
    };

     // [Perform a redo operation on the document, reimplementing the last change.]{: #UndoManager.redo}
     // @param {Boolean} dontSelect {:dontSelect}
     this.redo = function(dontSelect) {
        var deltas = this.$redoStack.pop();
        var redoSelectionRange = null;
        if (deltas) {
            redoSelectionRange =
                this.$doc.redoChanges(deltas, dontSelect);
            this.$undoStack.push(deltas);
            this.changeCount++;
            app.edits(this.changeCount)
        }

        return redoSelectionRange;
    };

     // Destroys the stack of undo and redo redo operations.
     this.reset = function() {
        this.$undoStack = [];
        this.$redoStack = [];
        this.changeCount = 0;
        app.edits(this.changeCount)
    };

    // state accessors
    this.hasUndo = function() {return this.$undoStack.length > 0; };
    this.hasRedo = function() {return this.$redoStack.length > 0; };
    this.markClean = function() {this.changeCount = 0; };
    this.isClean = function() {return this.changeCount === 0; };

}).call(UndoMgr.prototype);


ace.require("ace/ext/language_tools");
var Editor = function(elt){
    var dom = $(elt)
    var ed = ace.edit(dom.attr('id'))
    var undo = new UndoMgr()
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
            ed.commands.addCommands(PLOTDEVICE_KEYBINDINGS)
            ed.setOptions({
                enableBasicAutocompletion: true,
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
            _.each(_menu_cmds, function(cmds, menu){
                if (_.contains(cmds, cmd)) app.flash(menu)
            })
        },
        _scroll_h:function(x){
            var now = Date.now()
            if (_htimer) clearTimeout(_htimer)
            else{
                _hmin = now + 500
                dom.addClass('scrolling-h')
            }
            _htimer = setTimeout(function(){
                dom.removeClass('scrolling-h');
                _htimer=null
            }, Math.max(_hmin-now, 180))
        },
        _scroll_v:function(y){
            var now = Date.now()
            if (_vtimer) clearTimeout(_vtimer)
            else{
                _vmin = now + 500
                dom.addClass('scrolling-v')
            }
            _vtimer = setTimeout(function(){
                dom.removeClass('scrolling-v');
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
            dom.css({fontFamily:family, fontSize:px})
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
            console.log('tokens',_.map(tok, function(t){return t.type}))
            var at = sess.getTokenAt(rng.start.row,rng.start.column)
            _.each(tok, function(t, i){
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
                var anns = _.map(lines, function(line, i){
                    var ann = {row:line, col:0, type:"warning"}
                    if (i==0) _.extend(ann, {type:"error", text:err})
                    return ann
                })
                sess.setAnnotations(anns)
            }

        }
    }

    return (dom.length==0) ? {} : that.init()
}
