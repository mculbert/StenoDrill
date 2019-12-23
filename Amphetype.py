
from __future__ import with_statement, division

import os
import sys

# Get command-line --database argument before importing
# modules which count on database support
import optparse
opts = optparse.OptionParser()
opts.add_option("-d", "--database", metavar="FILE", help="use database FILE")
v = opts.parse_args()[0]

dbname = v.database
if dbname is None:
    import getpass
    try:
        dbname = getpass.getuser() or "StenoDrill"
        dbname += '.db'
    except:
        dbname = "StenoDrill.db"

import Data
Data.load_db(dbname)

from Data import DB
from Config import Settings
from Quizzer import Quizzer
from StatWidgets import StringStats
from TextManager import TextManager
from Performance import PerformanceHistory
from Config import PreferenceWidget
from Database import DatabaseWidget

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

QApplication.setStyle('cleanlooks')


class TyperWindow(QMainWindow):
    def __init__(self, *args):
        super(TyperWindow, self).__init__(*args)

        self.setWindowTitle("Amphetype")

        tabs = QTabWidget()

        quiz = Quizzer()
        tabs.addTab(quiz, "Typer")

        tm = TextManager()
        quiz.wantWords.connect(tm.genWords)
        tm.addWords.connect(quiz.addWords)
        tabs.addTab(tm, "Sources")

        ph = PerformanceHistory()
        tm.refreshSources.connect(ph.refreshSources)
        #quiz.statsChanged.connect(ph.updateData)
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


