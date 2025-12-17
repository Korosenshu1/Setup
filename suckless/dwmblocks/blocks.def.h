static const char date[] = "date -d 'now' +'%A %e (%b) - %H:%M'' '";
static const char pvol[] = "/home/manuel/.local/bin/vol-stat.sh";
static const char pbat[] = "/home/manuel/.local/bin/bat.sh";
static const char cpu_ram[] = "/home/manuel/.local/bin/cpu-ram.sh";
static const char netspeed[] = "/home/manuel/.local/bin/netspeed.sh";
static const char wifi[] = "/home/manuel/.local/bin/wifi.sh";
static const char bt[] = "/home/manuel/.local/bin/bt.sh";
static const char sysinfo[] = "/home/manuel/.local/bin/sysinfo.sh";
static const char netinfo[] = "/home/manuel/.local/bin/netinfo.sh";
static const Block blocks[] = {
	/*Icon*/	/*Command*/		/*Update Interval*/	/*Update Signal*/
//	{" 戦え - ",           NULL,                   0,                               0},
	{" ",                  sysinfo,                2,		    		0},
	{"",    	       netinfo,	       	       2,		 		0},
        {"",                   pvol,	               0,		                2},
	{"",                   pbat,	               2,		                0},
	{"",  	               bt,		       2,		                0},
	{"",  	               wifi,		       2,		                0},
	{"|  📅 ",  	       date,		       30,		                0},
};

//sets delimiter between status commands. NULL character ('\0') means no delimiter.
static char delim[] = "  ";
static unsigned int delimLen = 5;
