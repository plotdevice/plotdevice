PLOTDEVICE_KEYBINDINGS=[
    {
        name: "setneedle",
        bindKey: {mac: "Command-e"},
        exec: function(editor) {
            if (!editor.selection.isEmpty()){
                var needle = editor.getCopyText()
                app.setSearchPasteboard(needle)
                editor.$search.set({needle: needle});
            }
        }
    },{
        name: "blockoutdent",
        bindKey: {mac: "Command-["},
        exec: function(editor) { editor.blockOutdent(); },
        multiSelectAction: "forEachLine",
        scrollIntoView: "selectionPart"
    },{
        name: "blockindent",
        bindKey: {mac: "Command-]"},
        exec: function(editor) { editor.blockIndent(); },
        multiSelectAction: "forEachLine",
        scrollIntoView: "selectionPart"
    },{
        name: "refreshdoc",
        exec: function(editor, str) { editor.session.setValue(str); },
    },{
        name: "cancelRun",
        bindKey: {mac: "Command-."},
        exec: function(editor) {
            app.cancelRun()
        }
    },{
        name: "openPreferences",
        bindKey: {mac: "Command-,"},
        exec: function(editor) {
            app.loadPrefs()
        }
    // },{
    //     name: "showKeyboardShortcuts",
    //     bindKey: {mac: "Command-Alt-h"},
    //     exec: function(editor) {
    //         ace.config.loadModule("ace/ext/keybinding_menu", function(module) {
    //             module.init(editor);
    //             editor.showKeyboardShortcuts()
    //         })
    //     }
    },{
        name: "movelinesup",
        bindKey: "Alt-Up",
        exec: function(editor) {
            editor.moveLinesUp();
        },
        scrollIntoView: "cursor"
    }, {
        name: "movelinesdown",
        bindKey: "Alt-Down",
        exec: function(editor) {
            editor.moveLinesDown();
        },
        scrollIntoView: "cursor"
    }, {
        name: "modifyNumberUp",
        bindKey: "Ctrl-Up",
        exec: function(editor) { editor.modifyNumber(1); },
        multiSelectAction: "forEach"
    }, {
        name: "modifyNumberDown",
        bindKey: "Ctrl-Down",
        exec: function(editor) { editor.modifyNumber(-1); },
        multiSelectAction: "forEach"
    }, {
       name: "gotoline", // knock out the binding for the javascript-dialog version
        // bindKey: "Command-J",
        exec: function(editor) {},
        readOnly: true

    },{
        name: "gotostart",
        bindKey: "Home|Command-Up",
        exec: function(editor) { editor.navigateFileStart(); },
        multiSelectAction: "forEach",
        readOnly: true,
        scrollIntoView: "animate",
        aceCommandGroup: "fileJump"
    }, {
        name: "selecttostart",
        bindKey: "Shift-Home|Command-Shift-Up",
        exec: function(editor) { editor.getSelection().selectFileStart(); },
        multiSelectAction: "forEach",
        readOnly: true,
        scrollIntoView: "animate",
        aceCommandGroup: "fileJump"
    }, {
        name: "gotoend",
        bindKey: "End|Command-Down",
        exec: function(editor) { editor.navigateFileEnd(); },
        multiSelectAction: "forEach",
        readOnly: true,
        scrollIntoView: "animate",
        aceCommandGroup: "fileJump"
    }, {
        name: "selecttoend",
        bindKey: "Shift-End|Command-Shift-Down",
        exec: function(editor) { editor.getSelection().selectFileEnd(); },
        multiSelectAction: "forEach",
        readOnly: true,
        scrollIntoView: "animate",
        aceCommandGroup: "fileJump"
    }, {
        name: "selectOrFindNext", // knock out the binding for the javascript-dialog version
        // bindKey: "Command-J",
        exec: function(editor) {},
        readOnly: true
    },{
        name: "selectline",
        bindKey: "Command-L",
        exec: function(editor) {
            var sel = editor.getSelection()
            var rng = sel.getRange()
            console.log('rng start',rng.start.row,rng.start.column)
            console.log('rng end',rng.end.row,rng.end.column)
            rng.start.column=0
            sel.setSelectionRange(rng);
            sel.selectLineEnd();
            sel.selectRight();
       },
        multiSelectAction: "forEach",
        scrollIntoView: "cursor",
        readOnly: true
    },{
        name: "splitIntoLines",
        exec: function(editor) { editor.multiSelect.splitIntoLines(); },
        bindKey: "Command-Shift-L",
        readonly: true
    },{
        name: "expandSnippet",
        exec: function(editor) {
            if (!editor.completer)
                editor.completer = new Autocomplete();
            ed.completer.insertMatch()
        }
    },{
        name: "startAutocomplete",
        bindKey: "Ctrl-Space|Ctrl-Shift-Space|Alt-Space",
        exec: function(editor) {
            if (!editor.completer)
                editor.completer = new Autocomplete();
            editor.completer.showPopup(editor);
            // needed for firefox on mac
            editor.completer.cancelContextMenu();
        }
    }

]