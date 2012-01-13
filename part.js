function get_plural(in_int, str_sing, str_plural) {
    if (str_plural == undefined) str_plural = str_sing + "s";
    if (in_int == 1) {
        return in_int + " " + str_sing;
    } else {
        return in_int + " " + str_plural;
    }
}

function get_size_str(in_kb, float_ok) {
    if (float_ok) {
        var pf_lut = {1000000000 : "T",
                      1000000 : "G",
                      1000 : "M",
                      1 : "k"};
        for (var pf_value in pf_lut) {
            if (parseInt(in_kb / pf_value) > 0 || pf_value == 1) {
                size_str = parseFloat(in_kb / pf_value) + " " + pf_lut[pf_value] + "B";
                break;
            }
        }
    } else {
        if (in_kb == 0) {
            size_str = in_kb + " B";
        } else {
            var pf_lut = {1000000000 : "T",
                          1000000 : "G",
                          1000 : "M",
                          1 : "k"};
            for (var pf_value in pf_lut) {
                if (parseInt(in_kb / pf_value) * pf_value == in_kb) {
                    size_str = in_kb / pf_value + " " + pf_lut[pf_value] + "B";
                    break;
                }
            }
        }
    }
    return size_str;
}

function partition(p_idx, disk, new_base_defs) {
    this.partition_idx = p_idx;
    this.disk = disk;
    this.get_idx = function() {
        return this.partition_idx;
    }
    this.get_full_idx = function() {
        return this.disk.get_full_idx() + "." + this.get_idx();
    }
    var new_row = new $("<tr id=\"" + p_idx + "\" style=\"background-color:#ff3388\"></tr>");
    this.part_delete = $("<input type=\"button\" id=\"" + this.get_full_idx() + "\" value=\"delete partition\"/>");
    // hex id
    this.hex_id_field = $("<input type=\"text\" id=\"" + this.get_full_idx() + "\" size=\"4\" value=\"82\">");
    this.hex_id_field.change(function() {
        var element_ids = this.id.split(".");
        var partition_idx = parseInt(element_ids.shift());
        var disk_idx = parseInt(element_ids.shift());
        var part_idx = parseInt(element_ids.shift());
        part_tables[partition_idx].get_disk(disk_idx).get_partition(part_idx).set_hex_id(this.value);
    })
    new_row.append($("<td>" + this.disk.name + this.partition_idx + "</td>"));
    new_row.append($("<td></td>").append(this.part_delete));
    new_row.append($("<td></td>").append(this.hex_id_field));
    this.part_delete.click(function() {
        var element_ids = this.id.split(".");
        var partition_idx = parseInt(element_ids.shift());
        var disk_idx = parseInt(element_ids.shift());
        var part_idx = parseInt(element_ids.shift());
        part_tables[partition_idx].get_disk(disk_idx).remove_partition(part_idx);
    })
    this.remove_it = function() {
        this.partition_row.remove();
    }
    this.part_base_type = $("<select id=\"" + this.get_full_idx() + "\"/>");
    // add base types
    this.part_base_type.append("<option value=\"swap\">Swap</option>");
    this.part_base_type.append("<option value=\"ext\">Extended</option>");
    this.part_base_type.append("<option value=\"fs\">Filesystem</option>");
    this.part_base_type.append("<option value=\"pv\">PV (for LVM)</option>");
    this.part_base_type.append("<option value=\"unk\">Unknown</option>");
    this.part_base_type.change(function() {
        var element_ids = this.id.split(".");
        var partition_idx = parseInt(element_ids.shift());
        var disk_idx = parseInt(element_ids.shift());
        var part_idx = parseInt(element_ids.shift());
        part_tables[partition_idx].get_disk(disk_idx).get_partition(part_idx).set_part_type(this.value);
    })
    // bootable flag
    var bootable_flag = $("<input type=\"checkbox\" id=\"" + this.get_full_idx() + "\"/>");
    // filesystem list
    var filesystem_type = $("<select id=\"" + this.get_full_idx() + "\"/>");
    filesystem_type.append("<option value=\"reiserfs\">Reiserfs</option>");
    filesystem_type.append("<option value=\"ext2\">Ext2</option>");
    filesystem_type.append("<option value=\"ext3\">Ext3</option>");
    filesystem_type.append("<option value=\"xfs\">XFS</option>");
    filesystem_type.change(function() {
        var element_ids = this.id.split(".");
        var partition_idx = parseInt(element_ids.shift());
        var disk_idx = parseInt(element_ids.shift());
        var part_idx = parseInt(element_ids.shift());
        part_tables[partition_idx].get_disk(disk_idx).get_partition(part_idx).set_fs_type(this.value);
    })
    this.set_fs_type = function(fs_type) {
        filesystem_type.val(fs_type);
    }
    // fs_freq
    var fs_freq = $("<select id=\"" + this.get_full_idx() + "\"/>");
    fs_freq.append("<option value=\"0\">0</option>");
    fs_freq.append("<option value=\"1\">1</option>");
    this.set_fs_freq = function(new_val) {
        fs_freq.val(new_val);
    };
    // fs_passno
    var fs_passno = $("<select id=\"" + this.get_full_idx() + "\"/>");
    fs_passno.append("<option value=\"0\">0</option>");
    fs_passno.append("<option value=\"1\">1</option>");
    fs_passno.append("<option value=\"2\">2</option>");
    this.set_fs_passno = function(new_val) {
        fs_passno.val(new_val);
    };
    // size
    var fs_size = $("<input type=\"text\" id=\"" + this.get_full_idx() + "\" value=\"\"/>");
    fs_size.change(function() {
        var element_ids = this.id.split(".");
        var partition_idx = parseInt(element_ids.shift());
        var disk_idx = parseInt(element_ids.shift());
        var part_idx = parseInt(element_ids.shift());
        part_tables[partition_idx].get_disk(disk_idx).get_partition(part_idx).check_size(this.value);
    })
    // mountpoint and options
    var mountpoint = $("<input type=\"text\" id=\"" + this.get_full_idx() + "\" value=\"\"/>");
    mountpoint.change(function() {
        var element_ids = this.id.split(".");
        var partition_idx = parseInt(element_ids.shift());
        var disk_idx = parseInt(element_ids.shift());
        var part_idx = parseInt(element_ids.shift());
        part_tables[partition_idx].get_disk(disk_idx).get_partition(part_idx).set_mount_point(this.value);
    })
    var mountpoint_options = $("<input type=\"text\" id=\"" + this.get_full_idx() + "\" value=\"\"/>");
    mountpoint_options.change(function() {
        var element_ids = this.id.split(".");
        var partition_idx = parseInt(element_ids.shift());
        var disk_idx = parseInt(element_ids.shift());
        var part_idx = parseInt(element_ids.shift());
        part_tables[partition_idx].get_disk(disk_idx).get_partition(part_idx).set_mount_options(this.value);
    })
    this.set_mount_options = function(in_value) {
        in_value = $.trim(in_value);
        if (! in_value) {
            in_value = "defaults";
        }
        mountpoint_options.val(in_value);
    }
    this.set_mount_point = function(in_value) {
        in_value = $.trim(in_value).replace(/\s+/, "");
        if (! in_value) {
            in_value = "/";
        } else if (in_value[0] != "/") {
            in_value = "/";
        }
        mountpoint.val(in_value);
        this.disk.partition_table.check_validity();
    }
    var unused_elements = $("<div/>");
    this.set_part_type = function(t_str) {
        if (t_str == "ext") {
            if (this.disk.ext_part_defined && this.disk.ext_part_defined != this.partition_idx) {
                alert("Extended disk already defined (partition " + this.disk.ext_part_defined + "), bug found ?");
                t_str = "fs";
            } else {
                this.disk.set_ext_partition(this.partition_idx);
                this.disk.partitions_disable_type("ext", this.partition_idx);
            }
        } else if (this.disk.ext_part_defined == this.partition_idx) {
            this.disk.set_ext_partition(0);
            this.disk.partitions_enable_type("ext", this.partition_idx);
        }
        var has_mount_line = (act_fs == "fs");
        var has_size_line = (act_fs == "fs") || (act_fs == "swap") || (act_fs == "pv") || (act_fs == "unk")
        var need_mount_line = (t_str == "fs");
        var need_size_line = (t_str == "fs") || (t_str == "swap") || (t_str == "pv") || (t_str == "unk")
        if (has_size_line && ! need_size_line) {
            fs_size.parent().appendTo(unused_elements);
        }
        if (need_size_line && ! has_size_line) {
            new_row.append($("<td style=\"background-color:#ff7766\"></td>").append(fs_size));
        }
        if (has_mount_line && ! need_mount_line) {
            // remove mount line
            filesystem_type.parent().appendTo(unused_elements);
            mountpoint.parent().appendTo(unused_elements);
            mountpoint_options.parent().appendTo(unused_elements);
            bootable_flag.parent().appendTo(unused_elements);
            fs_freq.parent().appendTo(unused_elements);
            fs_passno.parent().appendTo(unused_elements);
        }
        if (need_mount_line && ! has_mount_line) {
            // add mount line
            new_row.append($("<td style=\"background-color:#ff7766\"></td>").append(filesystem_type));
            new_row.append($("<td style=\"background-color:#ff7766\"></td>").append(mountpoint));
            new_row.append($("<td style=\"background-color:#ff7766\"></td>").append(mountpoint_options));
            new_row.append($("<td style=\"background-color:#ff7766\"></td>").append(bootable_flag));
            new_row.append($("<td style=\"background-color:#ff7766\"></td>").append(fs_freq));
            new_row.append($("<td style=\"background-color:#ff7766\"></td>").append(fs_passno));
        }
        act_fs = t_str;
        this.part_base_type.val(t_str);
        if (t_str == "unk") {
            this.hex_id_field.removeAttr("disabled");
            this.set_hex_id("00", 1);
        } else {
            this.hex_id_field.attr("disabled", "true");
            this.set_hex_id({"fs"   : "82",
                             "swap" : "83",
                             "ext"  : "05",
                             "pv"   : "8e"}[t_str], 1);
        }
        this.disk.partition_table.check_validity();
    }
    this.set_hex_id = function(hex_id, no_check) {
        this.hex_id_field.val(hex_id);
        if (no_check != 1) {
            var new_base_type = {"82" : "fs",
                                 "83" : "swap",
                                 "05" : "ext",
                                 "8e" : "pv"}[hex_id];
            if (new_base_type != undefined) {
                this.set_part_type(new_base_type);
            }
        }
    }
    this.set_size = function(size_kb) {
        this.actual_size_kb = size_kb;
        fs_size.val(get_size_str(this.actual_size_kb));
    }
    this.check_size = function(in_kb) {
        parse_it = true;
        var in_kb = $.trim(in_kb).replace(/\s+/g, " ");
        in_parts = in_kb.split(" ");
        if (in_parts.length == 2) {
            var int_value = in_parts[0];
            var postfix = in_parts[1].toLowerCase();
        } else if (in_parts.length == 1) {
            var int_value = in_parts[0];
            var postfix = "mb";
        } else {
            alert("Cannot parse size of partition");
            this.set_size(this.actual_size_kb);
            parse_it = false;
        }
        if (parse_it) {
            var int_value = parseInt(int_value);
            if (int_value == "NaN") {
                alert("Cannot parse number");
                this.set_size(this.actual_size_kb);
            } else {
                var trans_map = {"mb" : 1000,
                                 "gb" : 1000000,
                                 "tb" : 1000000000,
                                 "m"  : 1000,
                                 "g"  : 1000000,
                                 "t"  : 1000000000};
                if (postfix in trans_map) {
                    this.set_size(int_value * trans_map[postfix]);
                } else {
                    alert("Cannot parse postfix");
                    this.set_size(this.actual_size_kb);
                }
            }
        }
    }
    this.enable_type = function(t_str) { this.part_base_type.find("[value=\"" + t_str + "\"]").removeAttr("disabled") ; } ;
    this.disable_type = function(t_str) { this.part_base_type.find("[value=\"" + t_str + "\"]").attr("disabled", "true") ; } ;
    // build row
    new_row.append($("<td style=\"background-color:#ff7766\"></td>").append(this.part_base_type));
    var act_fs = "None";
    if (new_base_defs == undefined) {
        this.set_part_type("fs");
        this.set_size(50000);
    } else {
        this.set_part_type(new_base_defs["base_type"]);
        this.set_size(new_base_defs["size"]);
    }
    this.check_validity = function(check_array) {
        check_array["partitions"] += 1;
        if (act_fs != "ext") check_array["size"] += this.actual_size_kb;
        if (act_fs == "fs") {
            check_array["size_fs"] += this.actual_size_kb;
            var act_mp = mountpoint.val();
            if (check_array["mount_points"].indexOf(act_mp) > -1) {
                var add_fname = "error_mount_points";
            } else {
                var add_fname = "mount_points";
            }
            check_array[add_fname].push(act_mp);
            check_array[add_fname].sort();
        }
    }
    this.set_mount_point("/");
    this.set_mount_options("defaults");
    if (this.disk.ext_part_defined) { this.disable_type("ext") ; } ;
    this.partition_row = new_row;
}

function disk(disk_name, partition_table) {
    this.name = disk_name;
    this.partition_table = partition_table;
    this.disk_idx = this.partition_table.disk_idx;
    this.get_idx = function() {
        return this.disk_idx;
    }
    this.get_full_idx = function() {
        return this.partition_table.get_idx() + "." + this.get_idx();
    }
    this.get_partition = function(part_idx) {
        return this.partition_list[part_idx];
    }
    var new_row = new $("<tr id=\"a\" style=\"background-color:#44ff00\"></tr>");
    var disk_td = new $("<td></td>");
    new_row.append(disk_td);
    this.disk_table = new $("<table style=\"border:1px solid;\"></table>");
    disk_td.append(this.disk_table);
    var info_row = $("<tr></tr>");
    this.info_row = info_row;
    this.disk_table.append(info_row);
    this.row = new_row;
    this.remove_it = function() {
        this.row.remove();
    }
    var used_partitions = 0;
    var free_partitions = [1, 2, 3, 4];
    this.partition_list = new Object();
    this.partitions_enable_type = function(t_str, skip_idx) {
        // iterates over defined partitions and enables a given part_type
        for (var part_idx in this.partition_list) {
            if (part_idx != skip_idx) { this.partition_list[part_idx].enable_type(t_str); } ;
        }
    }
    this.partitions_disable_type = function(t_str, skip_idx) {
        // iterates over defined partitions and disables a given part_type
        for (var part_idx in this.partition_list) {
            if (part_idx != skip_idx) { this.partition_list[part_idx].disable_type(t_str); } ;
        }
    }
    this.add_name_partition_line = function() {
        this.new_partition_sel = $("<select id=\"" + this.get_full_idx() + "\"/>");
        this.new_partition_sel.append("<option value=\"0\" selected>none</option>");
        this.modify_new_partition_line();
        this.disk_input = $("<input id=\"" + this.get_full_idx() + "\" value=\"" + disk_name + "\"/>");
        this.disk_delete = $("<input type=\"button\" id=\"" + this.partition_table.get_idx() + "." + this.get_idx() + "\" value=\"delete disk\"/>");
        this.disk_show = $("<input type=\"button\" id=\"" + this.partition_table.get_idx() + "." + this.get_idx() + "\" value=\"-\"/>");
        // add entities
        $("<td></td>").append("Disk Name: ", this.disk_input, ", New partition: ", this.new_partition_sel, ", delete disk: ", this.disk_delete, ", show: ", this.disk_show).appendTo(info_row);
        this.disk_delete.click(function() {
            var element_ids = this.id.split(".");
            var partition_idx = parseInt(element_ids.shift());
            var disk_idx = parseInt(element_ids.shift());
            part_tables[partition_idx].remove_disk(disk_idx);
            })
        this.disk_show.click(function() {
            var element_ids = this.id.split(".");
            var partition_idx = parseInt(element_ids.shift());
            var disk_idx = parseInt(element_ids.shift());
            part_tables[partition_idx].get_disk(disk_idx).toggle_show();
            })
        this.disk_input.change(function(event) {
            var element_ids = this.id.split(".");
            var partition_idx = parseInt(element_ids.shift());
            var disk_idx = parseInt(element_ids.shift());
            part_tables[partition_idx].new_disk_name_ok(disk_idx, this);
        })
        this.new_partition_sel.change(function() {
            if (this.value != 0) {
                var element_ids = this.id.split(".");
                var partition_idx = parseInt(element_ids.shift());
                var disk_idx = parseInt(element_ids.shift());
                part_tables[partition_idx].get_disk(disk_idx).new_partition(parseInt(this.value));
                this.value = 0;
            }
        })
    }
    this.toggle_show = function() {
        if (this.part_table.css("display") == "none") {
            this.part_table.css("display", "table");
            this.disk_show.val("-");
            this.new_partition_sel.removeAttr("disabled");
        } else {
            this.part_table.css("display", "none");
            this.disk_show.val("+");
            this.new_partition_sel.attr("disabled", "true");
        }
    }
    this.modify_new_partition_line = function() {
        // update new_partition_sel with possible values
        var sub_list = this.new_partition_sel.children();
        var add_list = free_partitions.slice(0, free_partitions.length);
        var remove_list = new Array();
        for (var idx=0; idx < sub_list.length; idx++) {
            sub_el = sub_list[idx];
            if (sub_el.value == 0) {
                // dummy value, ignore
                void 0;
            } else if (add_list.indexOf(parseInt(sub_el.value)) > -1) {
                // value in allowed list, pass
                add_list.splice(add_list.indexOf(parseInt(sub_el.value)), 1);
            } else {
                // remove value
                remove_list.push(idx);
            }
        }
        // remove elements
        if (remove_list.length) {
            remove_list.sort();
            remove_list.reverse();
            for (var idx=0; idx < remove_list.length; idx++) {
                var rem_el = remove_list[idx];
                jQuery(sub_list[rem_el]).remove();
            }
        }
        // add elements
        if (add_list.length) {
            add_list.sort();
            for (var idx=0; idx < add_list.length; idx++) {
                var free_part = add_list[idx];
                this.new_partition_sel.append("<option value=\"" + free_part + "\">part. " + free_part + "</option>");
            }
        }
    }
    this.new_partition = function(partition_idx, base_defs) {
        var ret_value = 0;
        if (partition_idx in this.partition_list) {
            alert("Partition " + partition_idx + " already used, internal error ?");
        } else {
            // add new partition
            used_partitions ++;
            var new_part = new partition(partition_idx, this, base_defs);
            ret_value = new_part;
            this.partition_list[partition_idx] = new_part;
            // add new partition if ext_part defined and this was the highest partition idx
            var act_max_part = Math.max.apply({}, free_partitions);
            // add all partitions from act_max_part up to partition_idx
            for (var add_p_idx = act_max_part; add_p_idx <= partition_idx; add_p_idx++) {
                if (free_partitions.indexOf(add_p_idx) == -1) { free_partitions.push(add_p_idx) ; } ; 
            }
            if (this.ext_part_defined && partition_idx >= act_max_part) {
                free_partitions.push(partition_idx + 1);
            }
            if (partition_idx > 4) {
                this.partition_list[this.ext_part_defined].part_delete.attr("disabled", "true");
                this.partition_list[this.ext_part_defined].part_base_type.attr("disabled", "true");
                this.ext_part_used = true ;
            } ;
            free_partitions.splice(free_partitions.indexOf(partition_idx), 1);
            this.modify_new_partition_line();
            // check for change in html elements
            if (used_partitions == 1) {
                this.header_line = new $("<tr id=\"header\"><td>Partition</td><td>delete</td><td>Hex</td><td>Type</td><td>Size</td></tr>");
                this.part_table.append(this.header_line);
                this.disk_input.attr("disabled", "true");
                this.disk_delete.attr("disabled", "true");
            }
            if (! free_partitions.length) this.new_partition_sel.attr("disabled", "true");
            var part_list = this.part_table.find("tr");
            var add_el = 0;
            if (part_list.length) {
                for (var idx=0; idx < part_list.length; idx++) {
                    var act_el = part_list[idx];
                    if (act_el.id != "header") {
                        if (parseInt(act_el.id) < partition_idx) add_el = act_el;
                    }
                }
            }
            if (add_el) {
                jQuery(add_el).after(new_part.partition_row);
            } else {
                //this.part_table.prepend(new_part.partition_row);
                new_part.partition_row.insertAfter(this.header_line);
                //header_line.prepend(new_part.partition_row);
            }
        }
        this.partition_table.check_validity();
        return ret_value;
    }
    this.remove_partition = function(partition_idx) {
        if (partition_idx in this.partition_list) {
            used_partitions--;
            this.partition_list[partition_idx].remove_it();
            delete this.partition_list[partition_idx];
            if (this.ext_part_defined == partition_idx) {
                // extended partition removed
                this.partitions_enable_type("ext");
                this.ext_part_defined = 0 ;
            } ; 
            free_partitions.push(partition_idx);
            // get maximum of used partitions
            var act_max_part = 0;
            for (var act_idx in this.partition_list) {
                act_max_part = Math.max(act_max_part, act_idx);
            }
            // remove free partitions which are too high
            // remove all free partitions which have a partition_idx > max_part_used + 1
            for (var act_idx = free_partitions.length; act_idx >= 0; act_idx--) {
                if (free_partitions[act_idx] > 4 && free_partitions[act_idx] > act_max_part + 1) {
                    free_partitions.splice(act_idx, 1);
                }
            }
            // max free_part
            var max_free_part = Math.max.apply({}, free_partitions);
            if (max_free_part <= 5 && this.ext_part_defined) {
                // we can delete the extended partiton
                this.partition_list[this.ext_part_defined].part_delete.removeAttr("disabled");
                this.partition_list[this.ext_part_defined].part_base_type.removeAttr("disabled");
            }
            this.modify_new_partition_line();
            // check for html elemnts change
            if (! used_partitions) {
                this.disk_input.removeAttr("disabled");
                this.disk_delete.removeAttr("disabled");
                this.header_line.remove();
            }
            if (free_partitions.length) this.new_partition_sel.removeAttr("disabled");
            this.partition_table.check_validity();
        }
    }
    this.set_ext_partition = function(part_idx) {
        this.ext_part_defined = part_idx;
        if (part_idx) {
            // add higher partition idxs
            free_partitions.push(5);
            this.new_partition_sel.removeAttr("disabled");
        } else {
            // remove higher partition idxs
            for (var idx=free_partitions.length-1; idx >= 0; idx --) {
                if (free_partitions[idx] > 4) { free_partitions.splice(idx, 1) ; } ; 
            }
        }
        this.modify_new_partition_line();
    }
    this.check_validity = function(check_array) {
        check_array["disks"] += 1;
        for (var part_idx in this.partition_list) {
            this.partition_list[part_idx].check_validity(check_array);
        }
    }
    this.part_table = $("<table></table>");
    this.add_name_partition_line();
    this.disk_table.append(($("<tr></tr>")).append($("<td colspan=\"3\"></td>").append(this.part_table)));
    // flags for sanity checks
    this.ext_part_defined = 0;
    // extended partition used
    this.ext_part_used = false;
}

function sys_partition(p_name, partition_table, new_base_defs) {
    this.partition_name = p_name;
    this.partition_table = partition_table;
    this.get_name = function() {
        return this.partition_name;
    }
    this.get_full_idx = function() {
        return this.partition_table.get_idx() + "." + this.get_name();
    }
    var new_row = new $("<tr style=\"background-color:#55ff3388\"></tr>");
    this.part_delete = $("<input type=\"button\" id=\"" + this.get_full_idx() + "\" value=\"delete partition\"/>");
    this.part_delete.click(function() {
        var element_ids = this.id.split(".");
        var partition_idx = parseInt(element_ids.shift());
        var part_name = element_ids.shift();
        part_tables[partition_idx].remove_sys_partition(part_name);
    })
    var mountpoint = $("<input type=\"text\" id=\"" + this.get_full_idx() + "\" value=\"\"/>");
    mountpoint.change(function() {
        var element_ids = this.id.split(".");
        var partition_idx = parseInt(element_ids.shift());
        var part_name = element_ids.shift();
        part_tables[partition_idx].get_sys_partition(part_name).set_mount_point(this.value);
    })
    var mountpoint_options = $("<input type=\"text\" id=\"" + this.get_full_idx() + "\" value=\"\"/>");
    mountpoint_options.change(function() {
        var element_ids = this.id.split(".");
        var partition_idx = parseInt(element_ids.shift());
        var part_name = element_ids.shift();
        part_tables[partition_idx].get_sys_partition(part_name).set_mount_options(this.value);
    })
    this.set_mount_options = function(in_value) {
        in_value = $.trim(in_value);
        if (! in_value) {
            in_value = "defaults";
        }
        mountpoint_options.val(in_value);
    }
    this.set_mount_point = function(in_value) {
        in_value = $.trim(in_value).replace(/\s+/, "");
        if (! in_value) {
            in_value = "/";
        } else if (in_value[0] != "/") {
            in_value = "/";
        }
        mountpoint.val(in_value);
        this.partition_table.check_validity();
    }
    this.check_validity = function(check_array) {
        check_array["sys_partitions"] += 1;
        var act_mp = mountpoint.val();
        if (check_array["mount_points"].indexOf(act_mp) > -1) {
            var add_fname = "error_mount_points";
        } else {
            var add_fname = "mount_points";
        }
        check_array[add_fname].push(act_mp);
        check_array[add_fname].sort();
    }
    new_row.append($("<td>" + this.partition_name + "</td>"));
    new_row.append($("<td></td>").append(this.part_delete));
    new_row.append($("<td></td>").append(mountpoint));
    new_row.append($("<td></td>").append(mountpoint_options));
    if (new_base_defs == undefined) {
        this.set_mount_point("/");
        this.set_mount_options("defaults");
    } else {
        this.set_mount_point(new_base_defs["mount_point"]);
        this.set_mount_options(new_base_defs["mount_options"]);
    }
    this.partition_row = new_row;
}

function partitiontable(table_idx) {
    this.out_table = $("<table style=\"border:2px solid;\"></table>");
    this.disk_table = new Object();
    this.sysfs_table = new Object();
    this.partition_table_idx = table_idx;
    this.sysfs_array = {"proc"       : [false, "/proc"                  , "defaults"],
                        "sysfs"      : [false, "/sys"                   , "defaults"],
                        "debugfs"    : [false, "/sys/kernel/debug"      , "defaults"],
                        "securityfs" : [false, "/"                      , "defaults"],
                        "usbfs"      : [false, "/proc/bus/usb"          , "defaults"],
                        "devpts"     : [false, "/dev/pts"               , "defaults"],
                        "nfsd"       : [false, "/proc/fs/nfsd"          , "defaults"],
                        "rpc_pipefs" : [false, "/var/lib/nfs/rcp_pipefs", "defaults"],
                        "configfs"   : [false, "/"                      , "defaults"]};
    this.disk_idx = 0;
    this.get_idx = function() {
        return this.partition_table_idx;
    }
    this.show = function() {
        this.out_table.appendTo($("#htp"));
    }
    this.add_disk = function(disk_name) {
        this.disk_idx++;
        this.disk_table[this.disk_idx] = new disk(disk_name, this);
        this.out_table.append(this.disk_table[this.disk_idx].row);
        this.check_validity();
        return this.disk_table[this.disk_idx];
    }
    this.get_disk = function(disk_id) {return this.disk_table[disk_id];};
    this.remove_disk = function(del_id) {
        this.disk_table[del_id].remove_it();
        delete this.disk_table[del_id];
        this.check_validity();
    }
    this.disk_name_in_use = function(new_name, ignore_idx) {
        // validate new disk
        var act_disk_names = new Object();
        for (var disk_id in this.disk_table) {
            if (disk_id != ignore_idx) {
                act_disk_names[this.disk_table[disk_id].name] = 1;
            }
        }
        return new_name in act_disk_names;
    }
    this.new_disk_name_ok = function(disk_idx, input_element) {
        if (this.disk_name_in_use(input_element.value, disk_idx)) {
            alert("Disk " + input_element.value + " already in use");
            input_element.value = this.disk_table[disk_idx].name;
        } else {
            this.disk_table[disk_idx].name = input_element.value;
        }
    }
    this.new_disk = function(new_id) {
        var ret_value = 0;
        if (this.disk_name_in_use(new_id)) {
            alert("Disk " + new_id + " already defined");
        } else if (new_id.substr(0, 5) != "/dev/") {
            alert("New disk has to start with /dev/");
        } else {
            disk_name = new_id.substr(5);
            if (! disk_name) {
                alert("Empty diskname");
            } else {
                ret_value = this.add_disk(new_id);
            }
        }
        return ret_value;
    }
    this.add_new_disk_line = function() {
        var input_el = $("<input id=\"" + this.get_idx() + "\" value=\"/dev/\"/>");
        var input_tr = $("<tr style=\"background-color:#334400;\"></tr>");
        this.sys_part_table = $("<table></table>");
        this.new_sys_part = $("<select id=\"" + this.get_idx() + "\"></select>");
        this.new_sys_part.append($("<option name=\"0\">none</option>"));
        this.out_table.append(input_tr);
        this.validity_div = $("<div></div>");
        input_tr.append($("<td style=\"background-color:#ddee00;\"></td>").append("New Disk: ", input_el, ", ", this.validity_div));
        this.out_table.append($("<tr style=\"background-color:#99f00f\"></tr>").append($("<td></td>").append(this.sys_part_table)));
        this.sys_part_table.append($("<tr></tr>").append($("<td>New system partition: </td>").append(this.new_sys_part)));
        this.modify_sysfs_line();
        this.new_sys_part.change(function() {
            if (this.value != 0) {
                var element_ids = this.id.split(".");
                var partition_idx = parseInt(element_ids.shift());
                part_tables[partition_idx].new_sys_partition(this.value);
                this.value = 0;
            }
        })
    }
    this.modify_sysfs_line = function() {
        for (var sys_name in this.sysfs_array) {
            var is_used = this.sysfs_array[sys_name][0];
            var is_present = this.new_sys_part.find("[value=" + sys_name + "]");
            if (! is_used && ! is_present.length) {
                this.new_sys_part.append($("<option name=\"" + sys_name + "\">" + sys_name + "</option>"));
            } else if (is_used && is_present) {
                is_present.remove();
            }
        }
    }
    this.remove_sys_partition = function(syspart_name) {
        if (syspart_name in this.sysfs_table) {
            this.sysfs_table[syspart_name].partition_row.remove();
            delete this.sysfs_table[syspart_name];
            this.sysfs_array[syspart_name][0] = false;
            this.modify_sysfs_line();
            this.check_validity();
        }
    }
    this.new_sys_partition = function(syspart_name, base_defs) {
        if (syspart_name in this.sysfs_table) {
            alert("System partition " + syspart_name + " already defined");
            return false;
        } else {
            if (base_defs == undefined) {
                base_defs = {"mount_point"   : this.sysfs_array[syspart_name][1],
                             "mount_options" : this.sysfs_array[syspart_name][2]};
            }
            var new_sysfs_part = new sys_partition(syspart_name, this, base_defs);
            this.sysfs_table[syspart_name] = new_sysfs_part;
            this.sys_part_table.append(new_sysfs_part.partition_row);
            this.sysfs_array[syspart_name][0] = true;
            this.modify_sysfs_line();
            this.check_validity();
        }
    }
    this.get_sys_partition = function(syspart_name) {
        return this.sysfs_table[syspart_name];
    }
    this.check_validity = function() {
        var check_array = {"disks"              : 0,
                           "partitions"         : 0,
                           "sys_partitions"     : 0,
                           "size"               : 0,
                           "size_fs"            : 0,
                           "mount_points"       : [],
                           "error_mount_points" : []};
        for (var disk_id in this.disk_table) {
            this.disk_table[disk_id].check_validity(check_array);
        }
        for (var sysp_name in this.sysfs_table) {
            this.sysfs_table[sysp_name].check_validity(check_array);
        }
        info_array = new Array();
        info_array.push(get_plural(check_array["disks"], "Disk"));
        info_array.push(get_plural(check_array["partitions"], "partition"));
        info_array.push(get_plural(check_array["sys_partitions"], "system partition"));
        var pt_valid = true;
        if (check_array["error_mount_points"].length) {
            pt_valid = false;
            info_array.push(get_plural(check_array["error_mount_points"].length, "problematic mount point") + ": " +
                            check_array["error_mount_points"].join(","));
        }
        if (check_array["mount_points"].indexOf("/") < 0) {
            pt_valid = false;
            info_array.push("No root mountpoint (/) defined");
        }
        info_array.push(get_size_str(check_array["size"], 1) + " total");
        info_array.push(get_size_str(check_array["size_fs"], 1) + " for filesystems");
        if (pt_valid) {
            info_array.push("Partitiontable is valid");
            this.validity_div.css("background-color", "#88ff88");
        } else {
            info_array.push("Partitiontable is invalid");
            this.validity_div.css("background-color", "#ff8888");
        }
        this.validity_div.text(info_array.join("; "));
    }
    this.add_new_disk_line();
    this.check_validity();
}

function init_ptable() {
    part_tables = [];
    part_tables[0] = new partitiontable(0);
    part_tables[0].show();
    // var new_disk = part_tables[0].new_disk("/dev/sda");
    var new_disk = part_tables[0].new_disk("/dev/sdb");
    var new_part = new_disk.new_partition(2);
    new_part.set_part_type("ext");
    new_disk.new_partition(1);
    new_disk.new_partition(4);
    new_disk.new_partition(5);
    new_disk.toggle_show();
    var new_disk = part_tables[0].new_disk("/dev/qwe");
    new_disk.toggle_show();
//    document.write(testj.test("qweqwiuqoezqwe"));
    $.ajax({
        async: false,
        type: "GET",
        url: "http://localhost/python/fetch_xml.py",
        dataType: "xml",
        //data: {type : "partition", "partition_idx" : 9},
        success: function(xml) {
            //alert(xml.getElementsByTagName("disc_name")[0].firstChild.nodeValue);
            $(xml).find("disc_list").find("disc").each(function() {
                var new_disk = part_tables[0].new_disk($(this).find("disc_name").text());
                $(this).find("partition").each(function() {
                    var base_type = $(this).find("base_type").text();
                    if (! base_type) {
                        var hex_id = $(this).find("hex_id").text();
                        // base type not set, try to interpret hex_id
                        if (hex_id == "05") {
                            base_type = "e";
                        }
                    }
                    if (! base_type) base_type = "u";
                    var pnum = parseInt($(this).find("num").text());
                    var new_base_type = {"s" : "swap",
                                         "e" : "ext",
                                         "l" : "pv",
                                         "f" : "fs",
                                         "u" : "unk"}[base_type];
                    var new_base_defs = {"base_type" : new_base_type,
                                         "size"      : parseInt($(this).find("size").text())};
                    var new_part = new_disk.new_partition(pnum, new_base_defs);
                    if (new_base_type == "unk") {
                        new_part.set_hex_id(hex_id);
                    }
                    if (new_base_type == "fs") {
                        new_part.set_fs_type($(this).find("fs_type").text());
                        new_part.set_fs_freq($(this).find("fs_freq").text());
                        new_part.set_fs_passno($(this).find("fs_passno").text());
                        new_part.set_mount_point($(this).find("mount_point").text());
                        new_part.set_mount_options($(this).find("mount_options").text());
                   }
                })
                new_disk.toggle_show();
            })
            $(xml).find("sys_partitions").find("sys_partition").each(function() {
                var sys_name = $(this).find("name").text();
                var new_part = part_tables[0].new_sys_partition(sys_name, {"mount_point"   : $(this).find("mountpoint").text(),
                                                                           "mount_options" : $(this).find("mount_options").text()});
            })
            //alert ($(xml).find("flags").text());//("bz2compression").attr("value"));
        },
        error: function(xhr, text_status, error_thrown) {
            alert("Error: " + text_status + "; " + [xhr.status, xhr.statusText].join(", "));
        },
    });
}
