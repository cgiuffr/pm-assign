# pm-assign

Assigns PMs for WP-based time recording. In other words, given a PM budget
and a Gantt chart of work packages over months, the script:
* Assigns PMs to each work package, by ensuring every given month is covered and by minimizing the number of unspent PMs per work package (leaving more unspent PMs for work packages ending later by default).
* Redistributes PMs per work package so they are as evenly spread out as possible.

Dependencies:
* Python 3.
* matplotlib.
* pulp.

Usage:

```shell
$ cp params_default.py params.py # and edit params.py
$ ./pm-assign.py
```