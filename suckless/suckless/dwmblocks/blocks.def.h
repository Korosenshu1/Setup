static const char date[] = "date -d 'now' +'%b %e (%a) - %H:%M'' '";
static const char pvol[] = "/home/manuel/.local/bin/vol-stat.sh";
static const char pbat[] = "/home/manuel/.local/bin/bat.sh";
static const char ram_used[] = "/home/manuel/.local/bin/ram_used.sh";
static const char cpu_perc[] = "/home/manuel/.local/bin/cpu_perc.sh";

//Modify this file to change what commands output to your statusbar, and recompile using the make command.
static const Block blocks[] = {
	/*Icon*/	/*Command*/		/*Update Interval*/	/*Update Signal*/
	{" C: ", cpu_perc,	5,		0},
	{"R: ", ram_used,	5,		0},

        {"",                   pvol,	               0,		                2},
	{"",                   pbat,	               10,		                0},
	{"|  ",  		   date,			60,		        0},
};

//sets delimiter between status commands. NULL character ('\0') means no delimiter.
static char delim[] = "  ";
static unsigned int delimLen = 5;
