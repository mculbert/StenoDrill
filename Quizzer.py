# -*- coding: UTF-8 -*-

from __future__ import with_statement, division


#import psyco
import platform
import collections
import time
import re
import random

from Data import Statistic, DB
from Config import Settings

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtCore import pyqtSignal as Signal
from QtUtil import *


if platform.system() == "Windows":
    # hack hack, hackity hack
    timer = time.clock
    timer()
else:
    timer = time.time

def rev(x): x.reverse(); return x


class Typer(QTextEdit):

    cancel = Signal()
    done = Signal()
    null_word = (None, None)
    
    def __init__(self, *args):
        super(Typer, self).__init__(*args)

        self.textChanged.connect(self.checkText)
        #self.setLineWrapMode(QTextEdit.NoWrap)
        self.target = None

    def sizeHint(self):
        return QSize(600, 10)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.cancel.emit()
        return QTextEdit.keyPressEvent(self, e)

    def setTarget(self,  text = null_word):
        self.editflag = True
        self.target = text[1]
        if Settings.get('ignore_case') and self.target is not None: self.target = self.target.lower()
        self.word_id = text[0]
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
        
        entered_text = self.toPlainText().strip()
        if Settings.get('ignore_case'): entered_text = entered_text.lower()
        if entered_text == self.target :
          self.done.emit()
        else :
          entered_chars = len(entered_text)
          if (entered_chars > len(self.target) or
              entered_text != self.target[0:entered_chars]) :
              self.mistroke = True

    def getStats(self):
        return self.word_id, self.target, (self.stroke_time - self.start_time), self.mistroke

class Quizzer(QWidget):

    def __init__(self, *args):
        super(Quizzer, self).__init__(*args)
        
        self.result = QLabel()
        self.typer = Typer()
        self.label = WWLabel()
        #self.label.setFrameStyle(QFrame.Raised | QFrame.StyledPanel)
        #self.typer.setBuddy(self.label)
        #self.info = QLabel()
        self.typer.done.connect(self.done)
        self.typer.cancel.connect(self.resetStats)
        Settings['typer_font'].change.connect(self.readjust)
        
        self.break_timer = QTimer()
        self.break_timer.setSingleShot(True)
        self.break_timer.timeout.connect(self.break_time)
        def reset_timer() :
            if Settings['breaks'].get() : self.break_time()
            else : self.break_timer.stop()
        Settings['minutes_in_sitting'].change.connect(reset_timer)
        Settings['breaks'].change.connect(reset_timer)

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
        if Settings.get('breaks') :
            self.break_timer.start(Settings.get('minutes_in_sitting') * 60000)
    
    def readjust(self):
        f = Settings.getFont("typer_font")
        self.label.setFont(f)
        self.typer.setFont(f)
    
    def clearWords(self):
        self.word_queue = []
        self.nextWord()
    
    def break_time(self):
        self.label.setText("Break time!\nWhen you've finished your break, hit the escape key (ESC) to start your drill.")
        self.typer.setTarget()
        DB.commit()
        
    def addWords(self):
        num_words = Settings.get('num_rand')
        # Check whether to activate new words
        if Settings.get('progressive'):
            num, seen, min_wpm, avg_wpm = DB.fetchall(
                '''select count(w.word), count((seen-mistakes) > %d), min(1.0/mpw), avg(1.0/mpw)
                   from active_words as w left join word_status as ws on (w.id = ws.word)''' %
                (Settings.get('prog_times'),))[0]
            if num == 0 or ((seen == num) and (min_wpm >= Settings.get('prog_min')) and (avg_wpm >= Settings.get('prog_avg'))):
                activate = DB.fetchall('''select w.rowid
                    from sources as s
                    join source_words as sw on (s.rowid = sw.source)
                    join words as w on (sw.word = w.rowid)
                    where s.active = 1 and w.active = 0
                    order by s.rowid, w.rowid
                    limit %d''' % (num_words,))
                DB.execute('update words set active = 1 where rowid in (%s)' %
                           ','.join([ str(row[0]) for row in activate ]))
        # Fetch random words, weighted by (mpw * (1+err_rate))^3
        dist = DB.execute('''select w.id, w.word, pow(mpw * (1+mistakes/seen), 3) as priority
            from active_words as w left join word_status as s on (w.id = s.word)
            order by priority asc''').fetchall()
        if len(dist) == 0 :
            return
        elif len(dist) == 1 :
            # We only have one word available, so replicate it
            self.word_queue = (dist * num_words) + self.word_queue
        elif len(dist) == 2 :
            words = (dist * (num_words // 2))
            if (num_words & 0x1) : # We need an odd number of words
                if (len(self.word_queue) == 0 or
                    self.word_queue[0][0] == words[-1][0]) :
                    # If the queue doesn't have any words or the second word
                    # of dist is the same as the first word currently in the
                    # queue, tack on the most common word (first of dist)
                    words.append(dist[0])
                else :
                    # The most common word (first of dict) is the same as the
                    # first word currently in the queue, so we don't want to
                    # tack that on to create a repetition. Instead, we'll
                    # tack on the second word of dict to the *front*.
                    words = [dist[1]] + words
            # Add the new words to the queue
            self.word_queue = words + self.word_queue
        else :
            avg_priority = 0
            count = 0
            for row in dist:
                if row[2] is not None:
                    avg_priority += row[2]
                    count += 1
            avg_priority = avg_priority / count if count > 0 else 1000.
            words = []
            while len(words) < num_words:
                for word in random.choices(dist, k = num_words - len(words),
                            weights = [ (row[2] if row[2] is not None else avg_priority)
                                        for row in dist ]):
                  if (len(words) == 0 or word[1] != words[-1][1]):
                      words.append(word)
            self.word_queue = words + self.word_queue

    def nextWord(self):
        num_show = Settings.get('num_rand')
        if len(self.word_queue) < num_show :
            self.addWords()
        if len(self.word_queue) == 0 :
            # No words available. Use placeholder text.
            self.label.setText("""Welcome to StenoDrill!\nA program that not only measures your speed and progress, but also helps you drill the briefs that holding you back the most. This is just a default text since your database is empty. Add lists of words to drill on the "Sources" tab. Then hit the escape key (ESC) to start your drill.""")
            self.typer.setTarget()
            return
        
        word = self.word_queue.pop()
        self.label.setText(' '.join(['<b>' + word[1] + '</b>'] +
            list(map(lambda x: x[1], rev(self.word_queue[(len(self.word_queue)-num_show+1):])))))
        self.typer.setTarget(word)
        self.typer.setFocus()

    def done(self):
        now = timer()
        word_id, word, word_time, mistroke = self.typer.getStats()
        mpw = word_time / (12.0 * len(word))

        # Don't record statistics for words < 6 WPM (ignoring word length)
        if word_time < 10.0 :
            self.wpm_num += 1.0 / mpw
            self.wpm_denom += 1
            self.acc_num += 1 - int(mistroke)
            self.acc_denom += 1
            self.result.setText("Speed: %.1fwpm\tAccuracy: %.1f%%" %
                                (self.wpm_num / self.wpm_denom,
                                 100. * self.acc_num / self.acc_denom))
            DB.execute('''insert into statistic (w,word,mpw,count,mistakes) values (?,?,?,?,?)''',
                       (now, word_id, mpw, 1, int(mistroke)))
        
        self.nextWord()
