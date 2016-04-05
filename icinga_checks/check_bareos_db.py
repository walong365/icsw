#!/usr/bin/python

# ---------------------------------------------------- #
# File : check_bareos_db
# Author : Philipp Posovszky, DLR
# E-Mail: Philipp.Posovszky@dlr.de
# Date : 22/04/2015
#
# Version: 1.0.3
#
# This program is free software; you can redistribute it or modify
# it under the terms of the GNU General Public License version 3.0
#
# Changelog:
# 	- 1.0.1 remove 'error' tapes from expire check and correct the help description 
#
#
# Plugin check for icinga
#
# Modified version 1.0.3 by www.init.at
# ---------------------------------------------------- #
import argparse
import psycopg2
import psycopg2.extras
import sys
#import subprocess
import MySQLdb 

# Variables
databaseName = 'bareos'

def create_backup_kind_string(full, inc, diff):
    if full == False and inc == False and diff == False:
        return "'F','D','I'"
    kind = []
    if full:
        kind.append("'F'")
    if inc:
        kind.append("'I'")
    if diff:
        kind.append("'D'")	

    return ",".join(kind)

def create_factor(unit):
    options = {'EB' : 2 ** 60,
               'PB' : 2 ** 50,
               'TB': 2 ** 40,
               'GB': 2 ** 30,
               'MB': 2 ** 20}
    return options[unit]

def get_state(state):
    options = {'T': '"Completed successfully"',
               'C': '"Created,not yet running"',
               'R': '"Running"',
               'E': '"Terminated with Errors"',
               'f': '"Fatal error"',
               'A': '"Canceled by user"'}
    return options[state]

def get_unit(time_unit):
    options = {'m' : "MINUTE",
               'h' : "HOUR",
               'D' : "DAY",
               'W' : "WEEK",
               'M' : "MONTH",
               'Y' : "YEAR"}
    return options[time_unit]

def check_failed_backups(courser, time, time_unit, unit, state, warning, critical):
    check_state = {}
    if time == None:
        time = 7
    state = ["'{}'".format(i) for i in state]
    if state == []:
        state = 'f'
    print state
    print ','.join(state)
    print get_state(state)
    query = """
    SELECT Job.Name,Level,starttime, JobStatus
    FROM Job
    Where JobStatus in (""" + ','.join(state) + """) and starttime > DATE_SUB(now(), INTERVAL """ + str(time) + """ """ + str(get_unit(time_unit)) + """);
    """
    print(query)
    courser.execute(query)
    results = courser.fetchall()  # Returns a value
    result = len(results)
    if result >= int(critical):
        check_state["returnCode"] = 2
        if time >= 1:
            check_state["returnMessage"] = "CRITICAL - " + str(result) + " " + str(get_state(state)) + " Backups in the past " + str(time) + " " + str(get_unit(time_unit)) + "'s"
        else:
            check_state["returnMessage"] = "CRITICAL - " + str(result) + " " + str(get_state(state)) + " Backups in the past " + str(time) + " " + str(get_unit(time_unit))
    elif result >= int(warning):
        check_state["returnCode"] = 1
        if time >= 1:
            check_state["returnMessage"] = "WARNING - " + str(result) +  " " + str(get_state(state)) + " Backups in the past " + str(time) + " " + str(get_unit(time_unit)) + "'s"
        else:
            check_state["returnMessage"] = "WARNING - " + str(result) +  " " + str(get_state(state)) + " Backups in the past " + str(time) + " " + str(get_unit(time_unit))
    else:
        check_state["returnCode"] = 0
        if result == 0:
            if time > 1:
                check_state["returnMessage"] = "OK - No Backups in state " + str(get_state(state)) + " in the last " + str(time) + " " + str(get_unit(time_unit)) + "'s"
            else:
                check_state["returnMessage"] = "OK - No Backups in state " + str(get_state(state)) + " in the last " + str(time) + " " + str(get_unit(time_unit))
        else:
            check_state["returnMessage"] = "OK - Only " + str(result) + " Backups in state " + str(get_state(state)) + " in the last " + str(time) + " " + str(get_unit(time_unit))
    check_state["performanceData"] = "Failed=" + str(result) + ";" + str(warning) + ";" + str(critical) + ";;"

    return check_state

def check_backupSize(courser, time, time_unit, kind, factor):
    if time != None:
        query = """
        SELECT ROUND(SUM(JobBytes/""" + str(float(factor)) + """),3)
        FROM Job
        Where Level in (""" + kind + """) and starttime > DATE_SUB(now(), INTERVAL """ + str(time) + """ """ + str(get_unit(time_unit)) + """);
        """
        print(query)
        courser.execute(query)
        results = courser.fetchone()  # Returns a value
        return results[0]
    else:
        query = """
        SELECT ROUND(SUM(JobBytes/""" + str(float(factor)) + """),3)
        FROM Job
        Where Level in (""" + kind + """);
        """
        print(query)
        courser.execute(query)
        results = courser.fetchone()  # Returns a value
        return results[0]
 
def checkTotalBackupSize(cursor, time, time_unit, kind, unit, warning, critical):
            check_state = {}
            result = check_backup_size(cursor, time, time_unit, kind, create_factor(unit))
            if result >= int(critical) or result == None:
                    check_state["returnCode"] = 2
                    if args.time:
                        if time > 1:
                            check_state["returnMessage"] = "CRITICAL - " + str(result) + " " + unit + " Total Backup size in Level " + kind + " in the past " + str(time) + " " + str(get_unit(time_unit)) + "'s"
                        else:
                            check_state["returnMessage"] = "CRITICAL - " + str(result) + " " + unit + " Total Backup size in Level " + kind + " in the past " + str(time) + " " + str(get_unit(time_unit))
                    else:
                        check_state["returnMessage"] = "CRITICAL - " + str(result) + " " +unit + " Total Backup size in level " + kind + " since first Backup"
            elif result >= int(warning):
                    check_state["returnCode"] = 1
                    if args.time:
                        if time > 1:
                            check_state["returnMessage"] = "WARNING - " + str(result) + " " + unit + " Total Backup size in Level " + kind + " in the past " + str(time) + " " + str(get_unit(time_unit)) + "'s"
                        else:
                            check_state["returnMessage"] = "WARNING - " + str(result) + " " + unit + " Total Backup size in Level " + kind + " in the past " + str(time) + " " + str(get_unit(time_unit))
                    else:
                        check_state["returnMessage"] = "WARNING - " + str(result) + " " +unit + " Total Backup size in level " + kind + " since first Backup"
            else:
                    check_state["returnCode"] = 0
                    if args.time:
                        if time > 1:
                            check_state["returnMessage"] = "OK - " + str(result) + " " + unit + " Total Backup size in Level " + kind + " in the past " + str(time) + " " + str(get_unit(time_unit)) + "'s"
                        else:
                            check_state["returnMessage"] = "OK - " + str(result) + " " + unit + " Total Backup size in Level " + kind + " in the past " + str(time) + " " + str(get_unit(time_unit))
                    else:
                        check_state["returnMessage"] = "OK - " + str(result) + " " + unit + " Total Backup size in level " + kind + " since first Backup"
            check_state["performanceData"] = "Size=" + str(result) + ";" + str(warning) + ";" + str(critical) + ";;"
            return check_state
        
def checkOversizedBackups(courser, time, time_unit, size, kind, unit, warning, critical):
            check_state = {}
            if time == None:
                time = 7
            factor = create_factor(unit)
            query = """
            SELECT Job.Name,Level,starttime, JobBytes/""" + str(float(factor)) + """
            FROM Job
            Where Level in (""" + kind + """) and starttime > DATE_SUB(now(), INTERVAL  """ + str(time) + """  """ + str(get_unit(time_unit)) + """)  and JobBytes/""" + str(float(factor)) + """>""" + str(size) + """;
            """
            print(query)
            courser.execute(query)
            results = courser.fetchall()  # Returns a value
            result = len(results) 
    
            if result >= int(critical):
                    check_state["returnCode"] = 2
                    if time > 1:
                        check_state["returnMessage"] = "CRITICAL - " + str(result) + " " + kind + " Backups larger than " + str(size) + " " + unit + " in the last " + str(time) + " " + str(get_unit(time_unit)) + "'s"
                    else:
                        check_state["returnMessage"] = "CRITICAL - " + str(result) + " " + kind + " Backups larger than " + str(size) + " " + unit + " in the last " + str(time) + " " + str(get_unit(time_unit))
            elif result >= int(warning):
                    check_state["returnCode"] = 1
                    if time > 1:
                        check_state["returnMessage"] = "WARNING - " + str(result) + " " + kind + " Backups larger than " + str(size) + " " + unit + " in the last " + str(time) + " " + str(get_unit(time_unit) + "'s")
                    else:
                        check_state["returnMessage"] = "WARNING - " + str(result) + " " + kind + " Backups larger than " + str(size) + " " + unit + " in the last " + str(time) + " " + str(get_unit(time_unit))
            else:
                    check_state["returnCode"] = 0
                    if time > 1:
                        check_state["returnMessage"] = "OK - No " + kind + " Backup larger than " + str(size) + " " + unit + " in the last " + str(time) + " " + str(get_unit(time_unit)) + "'s"
                    else:
                        check_state["returnMessage"] = "OK - No " + kind + " Backup larger than " + str(size) + " " + unit + " in the last " + str(time) + " " + str(get_unit(time_unit))
            check_state["performanceData"] = "OverSized=" + str(result) + ";" + str(warning) + ";" + str(critical) + ";;"
            return check_state

def checkEmptyBackups(cursor, time, time_unit, kind, warning, critical):
            check_state = {}
            if time == None:
                time = 7
            query = """
            SELECT Job.Name,Level,starttime
            FROM Job
            Where Level in (""" + str(kind) + """) and JobBytes=0 and starttime > DATE_SUB(now(), INTERVAL  """ + str(time) + """ """ + str(get_unit(time_unit)) + """) and JobStatus in ('T');
            """
            print(query)
            cursor.execute(query)
            results = cursor.fetchall()  # Returns a value
            result = len(results) 
            #print(time)
            if result >= int(critical):
                    check_state["returnCode"] = 2
                    if time > 1:
                        check_state["returnMessage"] = "CRITICAL - " + str(result) + " successful " + str(kind) + " backups are empty for the past " + str(time) + " " + str(get_unit(time_unit)) + "'s"
                    else:
                        check_state["returnMessage"] = "CRITICAL - " + str(result) + " successful " + str(kind) + " backups are empty for the past " + str(time) + " " + str(get_unit(time_unit))
            elif result >= int(warning):
                    check_state["returnCode"] = 1
                    if time > 1:
                        check_state["returnMessage"] = "WARNING - " + str(result) + " successful " + str(kind) + " backups are empty for the last " + str(time) + " " + str(get_unit(time_unit)) + "'s"
                    else:
                        check_state["returnMessage"] = "WARNING - " + str(result) + " successful " + str(kind) + " backups are empty for the last " + str(time) + " " + str(get_unit(time_unit))
            else:
                    check_state["returnCode"] = 0
                    check_state["returnMessage"] = "OK - All " + str(kind) + " backups are fine"
            check_state["performanceData"] = "EmptyBackups=" + str(result) + ";" + str(warning) + ";" + str(critical) + ";;"
            return check_state
               

# Checks on Jobs
def checkJobs(cursor, state, kind, time, time_unit, warning, critical):
    check_state = {}
    if time == None:
        time = 7
    query = """
    Select count(Job.Name)
    From Job
    Where Job.JobStatus like '""" + str(state) + """' and (starttime > DATE_SUB(now(), INTERVAL """ + str(time) + """ """ + str(get_unit(time_unit)) + """) or starttime IS NULL) and Job.Level in (""" + kind + """);
    """
    cursor.execute(query)
    results = cursor.fetchone()  # Returns a value 
    result = float(results[0])

    if result >= int(critical):
            check_state["returnCode"] = 2
            check_state["returnMessage"] = "CRITICAL - " + str(result) + " Jobs are in the state: "+str(get_state(state))
    elif result >= int(warning):
            check_state["returnCode"] = 1
            check_state["returnMessage"] = "WARNING - " + str(result) + " Jobs are in the state: "+str(get_state(state))
    else:
            check_state["returnCode"] = 0
            check_state["returnMessage"] = "OK - " + str(result) + " Jobs are in the state: "+str(get_state(state))
    check_state["performanceData"] = str(get_state(state))+"=" + str(result) + ";" + str(warning) + ";" + str(critical) + ";;"

    return check_state

def checkSingleJob(cursor, name, state, kind, time, warning, critical):
    check_state = {}
    if time == None:
        time = 7
    query = """
    Select Job.Name,Job.JobStatus, Job.Starttime
    FROM Job
    Where Job.Name like '%""" + name + """%' and Job.JobStatus like '""" + str(state) + """' and (starttime > DATE_SUB(now(), INTERVAL """ + str(time) + """ DAY) or starttime IS NULL) and Job.Level in (""" + kind + """);
    """
    cursor.execute(query)
    results = cursor.fetchall()  # Returns a value 
    result = len(results)

    if result >= int(critical):
            check_state["returnCode"] = 2
            check_state["returnMessage"] = "CRITICAL - " + str(result) + " Jobs are in the state: "+str(get_state(state))
    elif result >= int(warning):
            check_state["returnCode"] = 1
            check_state["returnMessage"] = "WARNING - " + str(result) + " Jobs are in the state: "+str(get_state(state))
    else:
            check_state["returnCode"] = 0
            check_state["returnMessage"] = "OK - " + str(result) + " Jobs are in the state: "+str(get_state(state))
    check_state["performanceData"] = str(get_state(state))+"=" + str(result) + ";" + str(warning) + ";" + str(critical) + ";;"

    return check_state

def checkRunTimeJobs(cursor, name, state, time, warning, critical):
    check_state = {}
    if time == None:
        time = 7
    query = """
    Select Count(Job.Name)
    FROM Job
    Where starttime > DATE_SUB(now(), INTERVAL """ + str(time) + """  HOUR) and Job.JobStatus like '""" + state + """';
    """
    cursor.execute(query)
    results = cursor.fetchone()  # Returns a value 
    result = float(results[0])

    if result >= int(critical):
            check_state["returnCode"] = 2
            check_state["returnMessage"] = "CRITICAL - " + str(result) + " Jobs are running longer than "+str(time)+" days"
    elif result >= int(warning):
            check_state["returnCode"] = 1
            check_state["returnMessage"] = "WARNING - " + str(result) + " Jobs are running longer than "+str(time)+" days"
    else:
            check_state["returnCode"] = 0
            check_state["returnMessage"] = "OK - " + str(result) + " Jobs are running longer than "+str(time)+" days"
    check_state["performanceData"] = "Count=" + str(result) + ";" + str(warning) + ";" + str(critical) + ";;"

    return check_state

     
# Checks on Tapes
def checkTapesInStorage(cursor, warning, critical):
    check_state = {}

    query = """
    SELECT count(MediaId)
    FROM Media,Pool,Storage
    WHERE Media.PoolId=Pool.PoolId
    AND Slot>0 AND InChanger=1
    AND Media.StorageId=Storage.StorageId;
    """
    cursor.execute(query)
    results = cursor.fetchone()  # Returns a value 
    result = float(results[0])
    
    if result <= int(critical):
        check_state["returnCode"] = 2
        check_state["returnMessage"] = "CRITICAL - Only " + str(result) + " Tapes are in the Storage"
    elif result <= int(warning):
        check_state["returnCode"] = 1
        check_state["returnMessage"] = "WARNING - Only" + str(result) + " Tapes are in the Storage"
    else:
        check_state["returnCode"] = 0
        check_state["returnMessage"] = "OK - " + str(result) + " Tapes are in the Storage"
    check_state["performanceData"] = "Tapes=" + str(result) + ";" + str(warning) + ";" + str(critical) + ";;"
    return check_state

def checkExpiredTapes(cursor, warning, critical):
    check_state = {}
    query = """
    SELECT Count(MediaId)
    FROM Media
    WHERE lastwritten+(media.volretention * '1 second'::INTERVAL)<now() and volstatus not like 'Error';
    """
    cursor.execute(query)
    results = cursor.fetchone()  # Returns a value 
    result = float(results[0])
    
    if result <= int(critical):
            check_state["returnCode"] = 2
            check_state["returnMessage"] = "CRITICAL - Only " + str(result) + " expired"
    elif result <= int(warning):
            check_state["returnCode"] = 1
            check_state["returnMessage"] = "WARNING - Only " + str(result) + " expired"
    else:
            check_state["returnCode"] = 0
            check_state["returnMessage"] = "OK - Tapes " + str(result) + " expired"
    check_state["performanceData"] = "Expired=" + str(result) + ";" + str(warning) + ";" + str(critical) + ";;"
    
    return check_state


def checkWillExpiredTapes(cursor, time, warning, critical):
    check_state = {}
    query = """
    SELECT Count(MediaId)
    FROM Media
    WHERE lastwritten+(media.volretention * '1 second'::INTERVAL)<now()+(""" + str(time) + """ * '1 day'::INTERVAL) and lastwritten+(media.volretention * '1 second'::INTERVAL)>now() and volstatus not like 'Error';;
    """
    cursor.execute(query)
    results = cursor.fetchone()  # Returns a value 
    result = float(results[0])
    
    if result <= int(critical):
            check_state["returnCode"] = 2
            check_state["returnMessage"] = "CRITICAL - Only " + str(result) + " will expire in next " + str(time) + " days"
    elif result <= int(warning):
            check_state["returnCode"] = 1
            check_state["returnMessage"] = "WARNING - Only " + str(result) + " will expire in next " + str(time) + " days"
    else:
            check_state["returnCode"] = 0
            check_state["returnMessage"] = "OK - Tapes " + str(result) + " will expire in next " + str(time) + " days"
    check_state["performanceData"] = "Expire=" + str(result) + ";" + str(warning) + ";" + str(critical) + ";;"
    
    return check_state

def checkReplaceTapes(cursor, mounts, warning, critical):
    check_state = {}
    query = """
    SELECT COUNT(VolumeName)
    FROM Media
    WHERE (VolErrors>0) OR (VolStatus='Error') OR (VolMounts>""" + str(mounts) + """) OR
    (VolStatus='Disabled');
    """
    cursor.execute(query)
    results = cursor.fetchone()  # Returns a value 
    result = float(results[0])

    if result >= int(critical):
            check_state["returnCode"] = 2
            check_state["returnMessage"] = "CRITICAL - " + str(result) + " Tapes have to be replaced in the near future"
    elif result >= int(warning):
            check_state["returnCode"] = 1
            check_state["returnMessage"] = "WARNING - Only " + str(result) + " Tapes have to be replaced in the near future"
    else:
            check_state["returnCode"] = 0
            check_state["returnMessage"] = "OK - Tapes " + str(result) + " have to be replaced in the near future"
    check_state["performanceData"] = "Replace=" + str(result) + ";" + str(warning) + ";" + str(critical) + ";;"

    return check_state

def checkEmptyTapes(courser, warning, critical):
        check_state = {}
        query = """
         SELECT Count(MediaId)
          FROM Media,Pool,Storage
          WHERE Media.PoolId=Pool.PoolId
          AND Slot>0 AND InChanger=1
          AND Media.StorageId=Storage.StorageId
          AND (VolStatus like 'Purged' or VolStatus like 'Recycle' or lastwritten+(media.volretention * '1 second'::INTERVAL)<now());
        """
        courser.execute(query)
        results = courser.fetchone()  # Returns a value 
        result = float(results[0])

        if result <= int(critical):
                check_state["returnCode"] = 2
                check_state["returnMessage"] = "CRITICAL - Only " + str(result) + " Tapes are empty in the Storage"
        elif result <= int(warning):
                check_state["returnCode"] = 1
                check_state["returnMessage"] = "WARNING - Only " + str(result) + " Tapes are empty in the Storage"
        else:
                check_state["returnCode"] = 0
                check_state["returnMessage"] = "OK - " + str(result) + " Tapes are empty in the Storage"
        check_state["performanceData"] = "Empty=" + str(result) + ";" + str(warning) + ";" + str(critical) + ";;"

        return check_state

def connectDB(userName, pw, hostName, database):
    if(database == "postgresql" or database == "p" or database == "psql"):
        try:
            # Define our connection string
            connString = "host='" + hostName + "' dbname='" + databaseName + "' user='" + userName + "' password='" + pw + "'"
            # get a connection, if a connect cannot be made an exception will be raised here
            conn = psycopg2.connect(connString)
            # conn.cursor will return a cursor object, you can use this cursor to perform queries
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
            return cursor 
        except psycopg2.DatabaseError, e:
            check_state = {}
            check_state["returnCode"] = 2
            check_state["returnMessage"] = "CRITICAL - " + str(e)[:-1]
            check_state["performanceData"] = ";;;;"
            printNagiosOutput(check_state)
         
    if(database == "mysql" or database == "m"):
        try:
            conn = MySQLdb.connect(host=hostName, user=userName, passwd=pw, db=databaseName)
            return conn.cursor() 
        except MySQLdb.Error, e:
                        check_state = {}
                        check_state["returnCode"] = 2
                        check_state["returnMessage"] = "CRITICAL - " + str(e)[:-1]
                        check_state["performanceData"] = ";;;;"
                        printNagiosOutput(check_state)
    
def printNagiosOutput(checkResult):
    if checkResult != None:
        print checkResult["returnMessage"] + "|" + checkResult["performanceData"]
        sys.exit(checkResult["returnCode"])
    else:
        print "Critical - Error in Script"
        sys.exit(2)

def argumentParser():
    parser = argparse.ArgumentParser(description='Check status of the bareos backups')
    group = parser.add_argument_group();
    group.add_argument('-u', '--user', dest='user', action='store', required=True, help='user name for the database connections')
    group.add_argument('-p', '--password', dest='password', action='store', help='password for the database connections', default="")
    group.add_argument('-H', '--Host', dest='host', action='store', help='database host', default="127.0.0.1")
    group.add_argument('-v', '--version', action='version', version='%(prog)s 1.0.0')
    parser.add_argument('-d', '--database', dest='database', choices=['mysql', 'm', 'postgresql', 'p', 'psql'], default='mysql', help='the database kind for the database connection (m=mysql, p=psql) (Default=Mysql)')
    
    subParser = parser.add_subparsers()
    
    jobParser = subParser.add_parser('job', help='Specific checks on a job');
    jobGroup = jobParser.add_mutually_exclusive_group(required=True)
    jobParser.set_defaults(func=checkJob) 
    jobGroup.add_argument('-js', '--checkJobs', dest='checkJobs', action='store_true', help='Check how many jobs are in a specific state [default=queued]')  
    jobGroup.add_argument('-j', '--checkJob', dest='checkJob', action='store_true', help='Check the state of a specific job [default=queued]')
    jobGroup.add_argument('-rt', '--runTimeJobs', dest='runTimeJobs', action='store_true', help='Check if a backup runs longer then n day')  
    jobParser.add_argument('-n', '--name', dest='name', action='store', help='Name of the job')
    jobParser.add_argument('-t', '--time', dest='time', action='store', help='Time in days (default=7 days)')
    jobParser.add_argument('-u', '--unit', dest='unit', choices=['GB', 'TB', 'PB'], default='TB', help='display unit')
    jobParser.add_argument('-w', '--warning', dest='warning', action='store', help='Warning value', default=5)
    jobParser.add_argument('-c', '--critical', dest='critical', action='store', help='Critical value', default=10)
    jobParser.add_argument('-st', '--state', dest='state', choices=['T', 'C', 'R', 'E', 'f','A'], default='C', help='T=Completed, C=Queued, R=Running, E=Terminated with Errors, f=Fatal error, A=Canceld by user [default=C]')
    jobParser.add_argument('-F', '--Full', dest='full', action='store_true', help='Backup kind full')
    jobParser.add_argument('-I', '--Inc', dest='inc', action='store_true', help='Backup kind inc')
    jobParser.add_argument('-D', '--Diff', dest='diff', action='store_true', help='Backup kind diff')
   
    tapeParser = subParser.add_parser('tape', help='Specific checks on a tapes');
    tapeGroup = tapeParser.add_mutually_exclusive_group(required=True);
    tapeParser.set_defaults(func=checkTape)
    tapeGroup.add_argument('-e', '--emptyTapes', dest='emptyTapes', action='store_true', help='Count empty tapes in the storage (Status Purged/Expired)')
    tapeGroup.add_argument('-ts', '--tapesInStorage', dest='tapesInStorage', action='store_true', help='Count how much tapes are in the storage')
    tapeGroup.add_argument('-ex', '--expiredTapes', dest='expiredTapes', action='store_true', help='Count how much tapes are expired')
    tapeGroup.add_argument('-wex', '--willExpire', dest='willExpire', action='store_true', help='Count how much tapes are will expire in n day')
    tapeGroup.add_argument('-r', '--replaceTapes', dest='replaceTapes', action='store_true', help='Count how much tapes should by replaced')
    tapeParser.add_argument('-w', '--warning', dest='warning', action='store', help='Warning value', default=5)
    tapeParser.add_argument('-c', '--critical', dest='critical', action='store', help='Critical value', default=10)
    tapeParser.add_argument('-m', '--mounts', dest='mounts', action='store', help='Amout of allowed mounts for a tape [used for replace tapes]', default=200)
    tapeParser.add_argument('-t', '--time', dest='time', action='store', help='Time in days (default=7 days)', default=7)


    statusParser = subParser.add_parser('status', help='Specific status informations');
    statusGroup = statusParser.add_mutually_exclusive_group(required=True);
    statusParser.set_defaults(func=checkStatus)
    statusGroup.add_argument('-b', '--totalBackupsSize', dest='totalBackupsSize', action='store_true', help='the size of all backups in the database [use time and kind for mor restrictions]')
    statusGroup.add_argument('-e', '--emptyBackups', dest='emptyBackups', action='store_true', help='Check if a successful backup have 0 bytes [only wise for full backups]')
    statusGroup.add_argument('-o', '--oversizedBackup', dest='oversizedBackups', action='store_true', help='Check if a backup have more than n TB')
    statusGroup.add_argument('-fb', '--failedBackups', dest='failedBackups', action='store_true', help='Check if a backup failed in the last n day')
    statusParser.add_argument('-F', '--Full', dest='full', action='store_true', help='Backup kind full')
    statusParser.add_argument('-I', '--Inc', dest='inc', action='store_true', help='Backup kind inc')
    statusParser.add_argument('-D', '--Diff', dest='diff', action='store_true', help='Backup kind diff')
    statusParser.add_argument('-tv', '--time_value', dest='time', action='store', help='Time value as integer, e.g. 13', type=int)
    statusParser.add_argument('-tu', '--time_unit', dest='time_unit',choices=['m', 'h', 'D', 'W', 'M', 'Y'], help='Time in m for MINUTE, h for HOUR, d for DAY, w for WEEK, m for MONTH and y for year (default=DAY)', default='D')
    statusParser.add_argument('-w', '--warning', dest='warning', action='store', help='Warning value [default=5]', default=5)
    statusParser.add_argument('-st', '--state', action='append', dest='state', help='T=Completed, C=Queued, R=Running, E=Terminated with Errors, f=Fatal error, A=Canceld by user [default=f]')
    statusParser.add_argument('-c', '--critical', dest='critical', action='store', help='Critical value [default=10]', default=10)
    statusParser.add_argument('-s', '--size', dest='size', action='store', help='Border value for oversized backups [default=2]', default=2)
    statusParser.add_argument('-u', '--unit', dest='unit', choices=['MB', 'GB', 'TB', 'PB', 'EB'], default='TB', help='display unit [default=TB]')
   

    return parser

def checkConnection(cursor):
    checkResult = {}
    if cursor == None:
        checkResult["returnCode"] = 2
        checkResult["returnMessage"] = "CRITICAL - No DB connection"
        printNagiosOutput(checkResult)
        return False
    else:
        return True

def checkTape(args):
    cursor = connectDB(args.user, args.password, args.host, args.database);
    checkResult = {}
    if checkConnection(cursor):     
        if args.emptyTapes:
            checkResult = checkEmptyTapes(cursor, args.warning, args.critical)
        if args.replaceTapes:
            checkResult = checkReplaceTapes(cursor, args.mounts, args.warning, args.critical)
        elif args.tapesInStorage:
            checkResult = checkTapesInStorage(cursor, args.warning, args.critical)
        elif args.expiredTapes:
            checkResult = checkExpiredTapes(cursor, args.warning, args.critical)        
        elif args.willExpire:
            checkResult = checkWillExpiredTapes(cursor, args.time, args.warning, args.critical)
        printNagiosOutput(checkResult);
        cursor.close();
        

def checkJob(args):
    cursor = connectDB(args.user, args.password, args.host, args.database);
    checkResult = {}
    if checkConnection(cursor):  
        if args.checkJob:
            kind = create_backup_kind_string(args.full, args.inc, args.diff)
            checkResult = checkSingleJob(cursor, args.name, args.state,kind, args.time, args.warning, args.critical) 
        elif args.checkJobs:
            kind = create_backup_kind_string(args.full, args.inc, args.diff)
            checkResult = checkJobs(cursor, args.state, args.kind, args.time, args.warning, args.critical) 
        elif args.runTimeJobs:
            checkResult = checkRunTimeJobs(cursor, args.name, args.state, args.time, args.warning, args.critical)
        printNagiosOutput(checkResult);
        cursor.close();

       
def checkStatus(args):
    cursor = connectDB(args.user, args.password, args.host, args.database);
    checkResult = {}
    if checkConnection(cursor):  
        if args.emptyBackups:
            kind = create_backup_kind_string(args.full, args.inc, args.diff)
            checkResult = checkEmptyBackups(cursor, args.time, args.time_unit, kind, args.warning, args.critical)        
        elif args.totalBackupsSize:
            kind = create_backup_kind_string(args.full, args.inc, args.diff)
            checkResult = checkTotalBackupSize(cursor, args.time, args.time_unit, kind, args.unit, args.warning, args.critical)  
        elif args.oversizedBackups:
            kind = create_backup_kind_string(args.full, args.inc, args.diff)
            checkResult = checkOversizedBackups(cursor, args.time, args.time_unit, args.size, kind, args.unit, args.warning, args.critical)   
        elif args.failedBackups:
            kind = create_backup_kind_string(args.full, args.inc, args.diff)
            checkResult = check_failed_backups(cursor, args.time, args.time_unit, args.unit, args.state, args.warning, args.critical)
        printNagiosOutput(checkResult);
        cursor.close();
              
    
if __name__ == '__main__':
    parser = argumentParser()
    args = parser.parse_args()
    # print parser.parse_args()
    args.func(args)
    # Get a cursor for the specific database connection
    
    


