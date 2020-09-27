# -* coding: utf-8 -*-
# vim-minimap is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# vim-minimap is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with vim-minimap. If not, see < http://www.gnu.org/licenses/ >.
#
# (C) 2014- by Séverin Lemaignan for the VIM integration, <severin@guakamole.org>
# (C) 2014- by Adam Tauber for the Drawille part, <asciimoo@gmail.com>

import os
import sys
import math
PY3 = sys.version_info[0] == 3

import vim

# Add the library to the Python path.
for p in vim.eval("&runtimepath").split(','):
    plugin_dir = os.path.join(p, "autoload", "drawille")
    if os.path.exists(plugin_dir):
        if plugin_dir not in sys.path:
            sys.path.append(plugin_dir)
        break

from drawille import *

WIDTH = 20
MINIMAP = "vim-minimap"

def getmmwindow():
    for b in vim.buffers:
        if b.name.endswith(MINIMAP):
            for w in vim.windows:
                if w.buffer == b:
                    return w
    return None

def getmainwindow():
    for b in vim.buffers:
        if not b.name.endswith(MINIMAP) and not "NERD_tree" in b.name:
            for w in vim.windows:
                if w.buffer == b:
                    return w
    return None

def setmmautocmd(clear = False):
    vim.command(":augroup minimap_group")
    vim.command(":autocmd!")
    if not clear:
        # Properly close the minimap when quitting VIM (ie, when minimap is the last remaining window
        vim.command(":autocmd WinEnter <buffer> if winnr('$') == 1|q|endif")
        vim.command(':autocmd CursorMoved,CursorMovedI,TextChanged,TextChangedI,BufWinEnter * MinimapUpdate')
    vim.command(":augroup END")

def toggleminimap():
    minimap = getmmwindow()
    if minimap:
        closeminimap()
    else:
        showminimap()

def showminimap():
    minimap = getmmwindow()

    # If the minimap window does not yet exist, create it
    if not minimap:
        # Save the currently active window to restore it later
        src = vim.current.window

        vim.command(":botright vnew %s" % MINIMAP)
        # make the new buffer 'temporary'
        vim.command(":setlocal buftype=nofile bufhidden=wipe noswapfile nobuflisted")
        # make ensure our buffer is uncluttered
        vim.command(":setlocal nonumber norelativenumber nolist nospell")

        # set all autocmds in a group
        setmmautocmd()
        minimap = vim.current.window
        minimap.width = WIDTH

        # fixed size
        vim.command(":set wfw")

        # Restore the active window
        vim.current.window = src

    updateminimap()

def updateminimap():
    minimap = getmmwindow()
    if not minimap:
        return

    src = vim.current.window

    if not hasattr(src, 'buffer'):
        return

    # Ignore NERD_tree Buffers
    # TODO make configurable
    if "NERD_tree" in src.buffer.name:
         return

    if src.buffer == minimap.buffer:
        return

    HORIZ_SCALE = 0.5

    mode = vim.eval("mode()")
    cursor = src.cursor

    vim.command("normal! H")
    topline = src.cursor[0]
    bottomline = topline + src.height - 1

    vim.current.window = minimap
    highlight_group = vim.eval("g:minimap_highlight")

    mmheight = 4 * minimap.height
    line_infos = [{'count': 0.0, 'weight': [0.0] * 2 * WIDTH} for _ in range(mmheight)]

    def char_weight(c):
        if c == ' ' or c == '\t':
            return 0.0
        if c == '.' or c == ',' or c == '\'':
            return 0.2
        if c == '|' or c == '-' or c == '#':
            return 2.0
        return 1.0

    heightrat = max(1.0, len(src.buffer) / mmheight)
    for y, line in enumerate(src.buffer):
        ymm = int(y / heightrat)
        line_infos[ymm]['count'] += 1.0 / HORIZ_SCALE
        for x, c in enumerate(line):
            xmm = int(x * HORIZ_SCALE)
            if xmm >= len(line_infos[ymm]['weight']):
                continue
            line_infos[ymm]['weight'][xmm] += char_weight(c)


    def draw(line_infos):
        c = Canvas()
        for y, info in enumerate(line_infos):
            for x in range(len(info['weight'])):
                if info['count'] == 0:
                    continue
                if info['weight'][x] / info['count'] >= 0.5:
                    c.set(x, y)
        # pad with spaces to ensure uniform block highlighting
        if PY3:
            return [line.ljust(WIDTH, u'\u00A0') for line in c.rows()]
        else:
            return [unicode(line).ljust(WIDTH, u'\u00A0') for line in c.rows()]

    vim.command(":setlocal modifiable")
    minimap.buffer[:] = draw(line_infos)
    # Highlight the current visible zone
    tmp = len(minimap.buffer) / len(src.buffer)
    top = min(len(minimap.buffer) - 1, int(topline * tmp))
    bottom = top + math.ceil(src.height * tmp)
    vim.command("match {0} /\\%>0v\\%<{1}v\\%>{2}l\\%<{3}l./".format(
        highlight_group, WIDTH + 1, top, bottom))

    # center the highlighted zone
    height = int(vim.eval("winheight(0)"))
    # first, put the cursor at the top of the buffer
    vim.command("normal! gg")
    # then, jump so that the active zone is centered
    if (top + (bottom - top) / 2) > height / 2:
        jump = min(top + (bottom - top) / 2 + height / 2, len(minimap.buffer))
        vim.command("normal! %dgg" % jump)

    # prevent any further modification
    vim.command(":setlocal nomodifiable")

    vim.current.window = src

    # restore the current selection if we were in visual mode.
    if mode in ('v', 'V', '\026'):
        vim.command("normal! gv")

    src.cursor = cursor

def closeminimap():
    minimap = getmmwindow()
    src = vim.current.window
    if minimap:
        vim.current.window = minimap
        # clear the minimap autocmds
        setmmautocmd(True)
        vim.command(":quit!")
        # try the last window, but sometimes this one was already closed
        # (ex. tagbar toggle) which will lead to an exception
        try:
            vim.current.window = src
        except:
            vim.current.window = vim.windows[0]

