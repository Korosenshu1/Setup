static const char date[] = "date -d 'now' +'%A %e (%b) - %H:%M'' '";
static const char pvol[] = "/home/manuel/.local/bin/vol-stat.sh";
static const char pbat[] = "/home/manuel/.local/bin/bat.sh";
static const char cpu_ram[] = "/home/manuel/.local/bin/cpu-ram.sh";
static const char netspeed[] = "/home/manuel/.local/bin/netspeed.sh";
static const char wifi[] = "/home/manuel/.local/bin/wifi.sh";
static const char bt[] = "/home/manuel/.local/bin/bt.sh";
//Modify this file to change what commands output to your statusbar, and recompile using the make command.
static const Block blocks[] = {
	/*Icon*/	/*Command*/		/*Update Interval*/	/*Update Signal*/
	{" ",                  cpu_ram,                5,		    		0},
	{"",    	       netspeed,	       2,		 		0},
        {"",                   pvol,	               0,		                2},
	{"",                   pbat,	               5,		                0},
	{"|",  	               bt,		       2,		                0},
	{"",  	               wifi,		       2,		                0},
	{"|  📅 ",  	       date,		       60,		                0},
};

//sets delimiter between status commands. NULL character ('\0') means no delimiter.
static char delim[] = "  ";
static unsigned int delimLen = 5;
