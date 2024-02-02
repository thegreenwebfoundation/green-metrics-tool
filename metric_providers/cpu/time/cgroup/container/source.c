#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <unistd.h>
#include <sys/time.h>
#include <time.h>
#include <string.h> // for strtok
#include <getopt.h>

typedef struct container_t { // struct is a specification and this static makes no sense here
    char path[BUFSIZ];
    char *id;
} container_t;

// All variables are made static, because we believe that this will
// keep them local in scope to the file and not make them persist in state
// between Threads.
// in any case, none of these variables should change between threads
static int user_id = 0;
static long int user_hz;
static unsigned int msleep_time=1000;

static long int read_cpu_cgroup(char* filename) {
    long int cpu_usage = -1;
    FILE* fd = NULL;
    fd = fopen(filename, "r");
    if ( fd == NULL) {
        fprintf(stderr, "Error - Could not open path for reading: %s. Maybe the container is not running anymore? Are you using --rootless mode? Errno: %d\n", filename, errno);
        exit(1);
    }
    fscanf(fd, "usage_usec %ld", &cpu_usage);
    fclose(fd);
    return cpu_usage;
}

static int output_stats(container_t *containers, int length) {
    struct timeval now;
    gettimeofday(&now, NULL);

    for(int i=0; i<length; i++) {
        printf("%ld%06ld %ld %s\n", now.tv_sec, now.tv_usec, read_cpu_cgroup(containers[i].path), containers[i].id);
    }
    usleep(msleep_time*1000);

    return 1;
}

static int parse_containers(container_t** containers, char* containers_string, int rootless_mode) {
    if(containers_string == NULL) {
        fprintf(stderr, "Please supply at least one container id with -s XXXX\n");
        exit(1);
    }

    *containers = malloc(sizeof(container_t));
    char *id = strtok(containers_string,",");
    int length = 0;

    for (; id != NULL; id = strtok(NULL, ",")) {
        //printf("Token: %s\n", id);
        length++;
        *containers = realloc(*containers, length * sizeof(container_t));
        (*containers)[length-1].id = id;
        if(rootless_mode) {
            sprintf((*containers)[length-1].path,
                "/sys/fs/cgroup/user.slice/user-%d.slice/user@%d.service/user.slice/docker-%s.scope/cpu.stat",
                user_id, user_id, id);
        } else {
            sprintf((*containers)[length-1].path,
                "/sys/fs/cgroup/system.slice/docker-%s.scope/cpu.stat",
                id);
        }
    }

    if(length == 0) {
        fprintf(stderr, "Please supply at least one container id with -s XXXX\n");
        exit(1);
    }
    return length;
}

static int check_system(int rootless_mode) {
    const char* check_path;

    if(rootless_mode) {
        check_path = "/sys/fs/cgroup/user.slice/cpu.stat";
    } else {
        check_path = "/sys/fs/cgroup/system.slice/cpu.stat";
    }
    
    FILE* fd = NULL;
    fd = fopen(check_path, "r");

    if (fd == NULL) {
        fprintf(stderr, "Couldn't open cpu.stat file at %s\n", check_path);
        exit(127);
    }
    fclose(fd);
    return 0;
}

int main(int argc, char **argv) {

    int c;
    int rootless_mode = 0; // docker root is default
    char *containers_string = NULL;  // Dynamic buffer to store optarg
    container_t *containers = NULL;
    int check_system_flag = 0;

    setvbuf(stdout, NULL, _IONBF, 0);
    user_hz = sysconf(_SC_CLK_TCK);
    user_id = getuid();

    static struct option long_options[] =
    {
        {"rootless", no_argument, NULL, 'r'},
        {"help", no_argument, NULL, 'h'},
        {"interval", no_argument, NULL, 'i'},
        {"containers", no_argument, NULL, 's'},
        {"check", no_argument, NULL, 'c'},
        {NULL, 0, NULL, 0}
    };

    while ((c = getopt_long(argc, argv, "ri:s:hc", long_options, NULL)) != -1) {
        switch (c) {
        case 'h':
            printf("Usage: %s [-i msleep_time] [-h]\n\n",argv[0]);
            printf("\t-h      : displays this help\n");
            printf("\t-s      : string of container IDs separated by comma\n");
            printf("\t-i      : specifies the milliseconds sleep time that will be slept between measurements\n");
            printf("\t-c      : check system and exit\n\n");

            struct timespec res;
            double resolution;

            printf("\tEnvironment variables:\n");
            printf("\tUserHZ\t\t%ld\n", user_hz);
            clock_getres(CLOCK_REALTIME, &res);
            resolution = res.tv_sec + (((double)res.tv_nsec)/1.0e9);
            printf("\tSystemHZ\t%ld\n", (unsigned long)(1/resolution + 0.5));
            printf("\tCLOCKS_PER_SEC\t%ld\n", CLOCKS_PER_SEC);
            exit(0);
        case 'i':
            msleep_time = atoi(optarg);
            break;
        case 'r':
            rootless_mode = 1;
            break;
        case 's':
            containers_string = (char *)malloc(strlen(optarg) + 1);  // Allocate memory
            strncpy(containers_string, optarg, strlen(optarg));
            break;
        case 'c':
            check_system_flag = 1;
            break;
        default:
            fprintf(stderr,"Unknown option %c\n",c);
            exit(-1);
        }
    }

    if(check_system_flag){
        exit(check_system(rootless_mode)); 
    }

    int length = parse_containers(&containers, containers_string, rootless_mode);

    while(1) {
        output_stats(containers, length);
    }

    free(containers); // since tools is only aborted by CTRL+C this is never called, but memory is freed on program end

    return 0;
}
