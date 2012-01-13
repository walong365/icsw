#!/bin/bash

ggroup_name=iwss
export=4060
export_scr=3726
home_server=fs3
sge_server=sge1
ggroup_idx=$(echo "SELECT ggroup_idx FROM ggroup WHERE ggroupname='$ggroup_name'" | mysql_session.sh | tail -1)

while read fname lname mail inst ; do
    # expand loginname unti a unique one is found
    idx=0
    while true ; do
	if [ $idx -gt 0 ] ; then
	    login="${fname:0:$idx}$lname"
	else
	    login=$lname
	fi
	login=$(echo $login | tr [:upper:] [:lower:])
	if [ $(echo "SELECT * FROM user WHERE login='$login'" | mysql_session.sh | wc -l) -gt 0 ] ; then
	    idx=$(( $idx + 1 ))
	else
	    break
	fi
    done
    # get uid
    uid=$(( $(echo "SELECT uid FROM user ORDER BY uid DESC LIMIT 1" | mysql_session.sh | tail -1) + 1))
    pwd=$(/usr/bin/python-init -c "import crypt; import random; print crypt.crypt(\"${login}128\", \"\".join([chr(random.randint(97, 122)) for x in range(16)]))")
    echo "Creating loginname $login ($fname, $lname), mail is $mail, comment is $inst"
    sql_str="INSERT INTO user SET active=1, login='$login', uid=$uid, ggroup=$ggroup_idx, export=$export, export_scr=$export_scr, home='$login', scratch='$login', shell='/bin/bash', password='$pwd', uservname='$fname', usernname='$lname', useremail='$mail', usercom='$inst' "
    echo $sql_str | mysql_session.sh
    # contact server
    send_command.py $home_server 8004 create_user_home username:$login
    send_command.py $sge_server 8004 create_sge_user username:$login
done < new_users.dat
