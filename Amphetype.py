
from __future__ import with_statement, division

import os
import sys


# Get command-line --database argument before importing
# modules which count on database support
from Config import Settings

import optparse
opts = optparse.OptionParser()
opts.add_option("-d", "--database", metavar="FILE", help="use database FILE")
v = opts.parse_args()[0]

if v.database is not None:
    Settings.set('db_name', v.database)

from Data import DB
from Quizzer import Quizzer
from StatWidgets import StringStats
from TextManager import TextManager
from Performance import PerformanceHistory
from Config import PreferenceWidget
from Database import DatabaseWidget

from PyQt4.QtCore import *
from PyQt4.QtGui import *

QApplication.setStyle('cleanlooks')


class TyperWindow(QMainWindow):
    def __init__(self, *args):
        super(TyperWindow, self).__init__(*args)

        self.setWindowTitle("Amphetype")

        tabs = QTabWidget()

        quiz = Quizzer()
        tabs.addTab(quiz, "Typer")

        tm = TextManager()
        self.connect(quiz, SIGNAL("wantWords"), tm.genWords)
        self.connect(tm, SIGNAL('addWords'), quiz.addWords)
        tabs.addTab(tm, "Sources")

        ph = PerformanceHistory()
        self.connect(tm, SIGNAL("refreshSources"), ph.refreshSources)
        #self.connect(quiz, SIGNAL("statsChanged"), ph.updateData)
        self.connect(ph, SIGNAL("gotoText"), lambda: tabs.setCurrentIndex(0))
        tabs.addTab(ph, "Performance")

        st = StringStats()
        tabs.addTab(st, "Analysis")

        dw = DatabaseWidget()
        tabs.addTab(dw, "Database")

        pw = PreferenceWidget()
        tabs.addTab(pw, "Preferences")

        ab = AboutWidget()
        tabs.addTab(ab, "About/Help")

        self.setCentralWidget(tabs)

        quiz.nextWord()

    def sizeHint(self):
        return QSize(650, 400)

class AboutWidget(QTextBrowser):
    def __init__(self, *args):
        html = "about.html file missing!"
        try:
            html = open("about.html", "r").read()
        except:
            pass
        super(AboutWidget, self).__init__(*args)
        self.setHtml(html)
        self.setOpenExternalLinks(True)
        #self.setMargin(40)
        self.setReadOnly(True)

app = QApplication(sys.argv)

w = TyperWindow()
w.show()

app.exec_()

print "exit"
DB.commit()


