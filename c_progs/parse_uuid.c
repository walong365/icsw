#define UUID_NAME "/etc/sysconfig/cluster/.cluster_device_uuid"

char* parse_uuid(src_ip) {
    char* identity_str = malloc(1000);
    identity_str[0] = 0;
    char* uuid_buffer = malloc(1000);
    int uuid_file = open(UUID_NAME, O_RDONLY);
    int i, colons_passed;
    struct utsname myuts;
    // get uts struct
    uname(&myuts);
    colons_passed = 0;
    if (uuid_file > 0) {
        read(uuid_file, uuid_buffer, 46);
        for (i = 0; i < strlen(uuid_buffer); i++) {
            if ((colons_passed > 1 || i > 17) && (uuid_buffer[i] != '\n')) sprintf(identity_str, "%s%c", identity_str, uuid_buffer[i]);
            if (uuid_buffer[i] == ':') colons_passed++;
        };
        close(uuid_file);
        sprintf(identity_str, "%s:%s:%s", identity_str, SERVICE_NAME, src_ip);
    } else {
        sprintf(identity_str, "%s:%s:%d", myuts.nodename, SERVICE_NAME, getpid());
    };
    return identity_str;
};
