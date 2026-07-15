// the language-tools extension provides snippets and autocomplete
ace.require("ace/ext/language_tools");
// the linking extension provides accel-hover/click token events (used for cmd-click docs links)
ace.require("ace/ext/linking");
// used to render usage-sample tooltips with the same tokenizer+theme as the live editor
var staticHighlight = ace.require("ace/ext/static_highlight");
var Range = ace.require("ace/range").Range;

// Wrap the ace UndoManager's mutation methods with callbacks to the pyobjc EditorView
// keeping it up-to-date on whether the file has been modified & whether undo/redo are available.
// Also send a copy of the buffer contents with each change so the EditorView's shadow copy is
// fresh enough to be read synchronously at save-time.
const {UndoManager:__UndoManager} = ace.require('ace/undomanager')
function UndoManager(){ __UndoManager.call(this) }
UndoManager.prototype = Object.create(__UndoManager.prototype);
for (const method of ['add', 'undo', 'redo', 'reset']){
    UndoManager.prototype[method] = function(){
        __UndoManager.prototype[method].call(this, ...arguments);
        app.sync_edits(this.$undoStack.length, window?.editor?.source?.() ?? null)
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
    var _linkMarker = null;
    var _altHeld = false;
    var _lastMouseEvent = null;
    var that = {
        init:function(){

            // configure the editor
            ed.setShowPrintMargin(false);
            ed.setFadeFoldWidgets(true);
            ed.setHighlightActiveLine(false);
            ed.setHighlightGutterLine(false);
            ed.commands.addCommands(PLOTDEVICE_KEYBINDINGS) // TODO: only apply when Default is chosen in prefs…
            ed.setOptions({
                enableBasicAutocompletion: true,
                // enableLiveAutocompletion: true,
                enableSnippets: true
            });
            ed.renderer.updateCharacterSize()
            ed.commands.on("afterExec", that._commandStream)
            ed.on("blur", that._blur)
            ed.on("focus", that._focus)

            // enable syntax-documentation tooltips
            ed.hoverTooltip.setDataProvider(that._sampleHover)
            ed.hoverTooltip.addToEditor(ed)

            // cmd-hover/cmd-click a mapped symbol to underline/open its docs.
            // $enableJumpToDef frees up plain cmd-click for this (multi-cursor-add
            // moves to cmd-option-click instead). registered before enableLinking so
            // it runs first and _altHeld is current by the time linkHover/linkClick
            // fire (ext-linking.js doesn't pass the alt-key state through itself)
            ed.on("mousemove", that._trackMouse)
            ed.on("click", that._trackMouse)
            ed.setOption("enableLinking", true)
            ed.$mouseHandler.$enableJumpToDef = true
            ed.on("linkHover", that._linkHover)
            ed.on("linkHoverOut", that._linkHoverOut)
            ed.on("linkClick", that._linkClick)

            // mousemove-driven hover only fires on actual pointer movement, so
            // pressing/releasing cmd while stationary over a symbol wouldn't
            // otherwise show/hide the underline -- re-check the last known
            // mouse position directly against cmd's/option's keydown/keyup instead
            document.addEventListener('keydown', that._trackModifiers, true)
            document.addEventListener('keyup', that._trackModifiers, true)

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
            return that
        },
        _commandStream:function(e){
            // listen for commands that have key equivalents in the main menu and notify the
            // objc side of things when one of them is entered
            var cmd = e.command.name
            for (const [cmds, menu] of Object.entries(_menu_cmds)){
                if (cmds.includes(cmd)) app.flash_menu(menu)
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
            that._linkHoverOut()
        },

        _trackMouse:function(e){
            // ext-linking.js's linkHover/linkClick events don't carry the raw dom
            // event, so track option/alt ourselves to know whether it's held
            // alongside cmd (in which case ace's own cmd-option-click add-cursor
            // gesture should win instead of the docs link) -- also cache the
            // event itself so _trackModifiers can re-derive hover state against
            // the last known mouse position when cmd/option change while stationary
            _altHeld = !!(e.domEvent && e.domEvent.altKey)
            _lastMouseEvent = e
        },
        _trackModifiers:function(e){
            // pressing/releasing cmd or option alone doesn't fire a mousemove, so
            // ext-linking.js never re-evaluates the token under a stationary pointer
            // -- do it ourselves. modifier flags on the event reflect live state
            // (including for the key's own keyup), so no keydown/keyup branching
            // is needed -- just recompute from current state each time
            if ((e.key !== 'Meta' && e.key !== 'Alt') || !_lastMouseEvent) return
            _altHeld = !!e.altKey
            if (!e.metaKey || _altHeld){
                that._linkHoverOut()
                return
            }
            var docPos = _lastMouseEvent.getDocumentPosition()
            that._linkHover({position:docPos, token:sess.getTokenAt(docPos.row, docPos.column)})
        },
        _linkHover:function(e){
            var word = e.token && e.token.value
            if (_altHeld || that._isBindingTarget(e.token) || !PLOTDEVICE_SYMBOL_DOCS.hasOwnProperty(word)){
                that._linkHoverOut()
                return
            }
            that._linkHoverOut()
            ed.renderer.setCursorStyle("pointer") // .ace_layer has pointer-events:none, so css :hover/cursor on the marker itself has no effect
            var row = e.position.row
            var range = Range.fromPoints({row:row, column:e.token.start}, {row:row, column:e.token.start+e.token.value.length})
            // addMarker(..., "text") goes through drawTextMarker, which is built for
            // multi-row wrapped spans (wrong width + rounded corners for a single-row
            // range) -- draw a plain single-line underline via the same primitive
            // ace uses for selection/highlight markers instead. a dynamic marker must
            // NOT have a .range property or ace routes it through the static-marker
            // path (using its .clazz, which we don't set) instead of calling .update()
            _linkMarker = sess.addDynamicMarker({
                update: function(html, markerLayer, session, config){
                    markerLayer.drawSingleLineMarker(html, range, "ace_symbol-doc-link", config)
                }
            })
        },
        _linkHoverOut:function(){
            if (_linkMarker!=null) sess.removeMarker(_linkMarker.id)
            _linkMarker = null
            ed.renderer.setCursorStyle("")
        },
        _isBindingTarget:function(token){
            // spot locations where a term is being used as a kwarg (or other assignment), so we can 
            // exclude it from the command-click-for-docs behavior (since it would only coincidentally 
            // share the name of a documented function in that case)
            return !!token && (token.type === "variable.parameter" || token.type === "variable.assignment")
        },
        _sampleHover:function(e, editor){
            var pos = e.getDocumentPosition()
            var token = sess.getTokenAt(pos.row, pos.column)
            var word = token && token.value

            // don't show tooltip for kwargs if the docs are for a function
            if (!token || that._isBindingTarget(token) || !PLOTDEVICE_SYMBOL_USAGE.hasOwnProperty(word)) return
            var range = Range.fromPoints({row:pos.row, column:token.start}, {row:pos.row, column:token.start+token.value.length})
            var text = PLOTDEVICE_SYMBOL_USAGE[word].join("\n")

            // use syntax highlighting to style the usage sample
            staticHighlight.render(text, sess.getMode(), ed.getTheme(), 1, true, function(result){
                var tooltip = document.createElement("div")
                tooltip.innerHTML = result.html

                // add a link to the docs page (if applicable)
                var url = PLOTDEVICE_SYMBOL_DOCS[word]
                if (url){
                    var more = document.createElement("div")
                    more.className = "ace_symbol-doc-more"
                    more.style.color = getComputedStyle(dom).color
                    var moreText = document.createElement("span")
                    moreText.textContent = "read more…"
                    more.appendChild(moreText)
                    more.addEventListener("click", function(){ app.openDoc(url) })
                    tooltip.appendChild(more)
                }

                // default tooltip style is too specific to override with css, so manully set background to match theme
                ed.hoverTooltip.getElement().style.backgroundColor = getComputedStyle(dom).backgroundColor
                ed.hoverTooltip.showForRange(editor, range, tooltip, e)
            })
        },
        _linkClick:function(e){
            if (_altHeld) return // let ace's own cmd-option-click add-cursor gesture proceed instead
            if (that._isBindingTarget(e.token)) return // kwargs/assignments never have cmd-clickable docs
            var word = e.token && e.token.value
            var url = PLOTDEVICE_SYMBOL_DOCS[word]
            if (url) app.openDoc(url)
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
            dom.style.fontSize = `${px}px`
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
            // console.log('tokens', tok.map(t => t.type))
            var at = sess.getTokenAt(rng.start.row,rng.start.column)
            // tok.forEach((t, i) => {
            //     if (t===at) console.log('FOUND', t,'at',i)
            // })
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
