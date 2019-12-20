# -*- coding: UTF-8 -*-

from __future__ import with_statement, division


#import psyco
import platform
import collections
import time
import re

from Data import Statistic, DB
from Config import Settings

from PyQt4.QtCore import *
from PyQt4.QtGui import *
from QtUtil import *


if platform.system() == "Windows":
    # hack hack, hackity hack
    timer = time.clock
    timer()
else:
    timer = time.time


class Typer(QTextEdit):
    def __init__(self, *args):
        super(Typer, self).__init__(*args)

        self.connect(self, SIGNAL("textChanged()"), self.checkText)
        #self.setLineWrapMode(QTextEdit.NoWrap)
        self.target = None

    def sizeHint(self):
        return QSize(600, 10)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.emit(SIGNAL("cancel"))
        return QTextEdit.keyPressEvent(self, e)

    def setTarget(self,  text):
        self.editflag = True
        self.target = text
        self.start_time = self.stroke_time = timer()
        self.stroke_count = 0
        self.mistroke = False
        self.clear()
        self.editflag = False

    def checkText(self):
        if self.target is None or self.editflag:
            return
        
        now = timer()
        # Is this a new stroke (or additional characters of existing stroke)?
        if now - self.stroke_time > .05 : self.stroke_count += 1
        self.stroke_time = now
        
        entered_text = self.toPlainText().trimmed()
        if entered_text == self.target :
          self.emit(SIGNAL('done'))
        else :
          entered_chars = len(entered_text)
          if (entered_chars > len(self.target) or
              entered_text != self.target[0:entered_chars]) :
              self.mistroke = True

    def getStats(self):
        return self.target, (self.stroke_time - self.start_time), self.mistroke

class Quizzer(QWidget):
    def __init__(self, *args):
        super(Quizzer, self).__init__(*args)
        
        self.result = QLabel()
        self.typer = Typer()
        self.label = WWLabel()
        #self.label.setFrameStyle(QFrame.Raised | QFrame.StyledPanel)
        #self.typer.setBuddy(self.label)
        #self.info = QLabel()
        self.connect(self.typer,  SIGNAL("done"), self.done)
        self.connect(self.typer,  SIGNAL("cancel"), self.resetStats)
        self.connect(Settings, SIGNAL("change_typer_font"), self.readjust)

        self.word_queue = []

        layout = QVBoxLayout()
        #layout.addWidget(self.info)
        #layout.addSpacing(20)
        layout.addWidget(self.result, 0, Qt.AlignRight)
        layout.addWidget(self.label, 1, Qt.AlignBottom)
        layout.addWidget(self.typer, 1)
        self.setLayout(layout)
        self.readjust()
        self.resetStats()

    def resetStats(self):
        self.wpm_num = 0
        self.wpm_denom = 0
        self.acc_num = 0
        self.acc_denom = 0
        self.result.setText('')
        self.nextWord()
    
    def readjust(self):
        f = Settings.getFont("typer_font")
        self.label.setFont(f)
        self.typer.setFont(f)
    
    def addWords(self, words):
        self.word_queue = words + self.word_queue

    def nextWord(self):
        num_show = Settings.get('num_rand')
        if len(self.word_queue) < num_show :
            self.emit(SIGNAL('wantWords'))
        if len(self.word_queue) == 0 :
            # No words available. Use placeholder text.
            self.label.setText("""Welcome to StenoDrill!\nA program that not only measures your speed and progress, but also helps you drill the briefs that holding you back the most. This is just a default text since your database is empty. Add lists of words to drill on the "Sources" tab. Then hit the escape key (ESC) to start your drill.""")
            return
        
        word = self.word_queue.pop()
        queue_len = len(self.word_queue)
        self.label.setText(' '.join(['<b>' + word + '</b>'] +
            self.word_queue[queue_len:(queue_len-num_show+1):-1]))
        self.typer.setTarget(word)
        self.typer.setFocus()

    def done(self):
        now = timer()
        word, word_time, mistroke = self.typer.getStats()

        self.wpm_num += 12.0 * len(word) / word_time
        self.wpm_denom += 1
        self.acc_num += 1 - int(mistroke)
        self.acc_denom += 1
        self.result.setText("Speed: %.1fwpm\tAccuracy: %.1f%%" %
                            (self.wpm_num / self.wpm_denom,
                             100. * self.acc_num / self.acc_denom))

        DB.execute('''insert into statistic
            (time,w,count,mistakes,data) values (?,?,?,?,?)''',
            (word_time / len(word), now, 1, int(mistroke), word))
        
        self.nextWord()
