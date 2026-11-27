# 19. Project schedules are a separate generator that writes MSPDI

Status: Accepted

## Context

A tool that reads project plans needs synthetic plans with linked tasks, a calendar, costs, duration ranges and risk events. The repo had no schedule data. Output must be the same on every run for a given seed, runtime dependencies stay empty, and existing output must not change.

## Decision

`synthbiz project` writes project.xml, ranges.csv, risks.csv, data_dictionary.md, README.txt and manifest.json. The generator is in `src/synthbiz/project.py`, the XML writer in `src/synthbiz/mspdi.py` and the folder writer in `src/synthbiz/project_files.py`. It has its own random stream, as in ADR 17.

Network:

- Phases in order. Each phase is one summary task, layers of work tasks and one milestone in the last layer. UIDs and IDs count from 1 in outline order.
- Every link goes from an earlier layer to a later layer. A summary link goes from one phase, or its summary task, to the next phase or its summary task. So the graph of task starts and finishes has no cycle. Summary links are FS or SS.
- Every work task has an FS or FF successor. Work tasks that would lack one, and the last layer of a phase, link FS to the milestone.
- Four links are picked to hold the four types. Among them the FS link gets a negative lag and the SS link a positive lag.

MSPDI names and units, read on 2026-11-27:

- Link Type is 0 for FF, 1 for FS, 2 for SF and 3 for SS: https://learn.microsoft.com/en-us/office-project/xml-data-interchange/type-element-multiple-parents
- LinkLag is in tenths of a minute: https://learn.microsoft.com/en-us/office-project/xml-data-interchange/linklag-element
- Element names and order follow the schema pages for tasks, calendars and the project: https://learn.microsoft.com/en-us/office-project/xml-data-interchange/xml-schema-for-the-tasks-element , https://learn.microsoft.com/en-us/office-project/xml-data-interchange/xml-schema-for-the-calendars-element and https://learn.microsoft.com/en-us/office-project/xml-data-interchange/xml-schema-for-the-project-element
- Durations use the PnYnMnDTnHnMnS form: https://learn.microsoft.com/en-us/office-project/xml-data-interchange/introduction-to-project-xml-data
- DayType 1 is Sunday: https://learn.microsoft.com/en-us/office-project/xml-data-interchange/daytype-element
- The Microsoft pages named here do not state the unit of Cost and FixedCost. The files hold hundredths of the currency unit, which is how the third party reader MPXJ reads them (parseCurrency divides by 100): https://github.com/joniles/mpxj/blob/master/src/main/java/org/mpxj/mspdi/DatatypeConverter.java

The schema file is not copied into the repo. The tests compare the XML with names, order and codes written by hand. They do not validate against the schema and do not open the file in Microsoft Project.

Sidecar files:

- ranges.csv gives min, most_likely and max as whole percent of plan duration. The unit is written in README.txt, data_dictionary.md and manifest.json, and the header has no unit column.
- risks.csv gives each event a probability, one distribution name for both impacts, a triple in working minutes, a triple in cents, the affected task UIDs joined by `|` and an optional group name.

Calendar: the start date moves to a working day. A bound on the longest path adds, per layer, the longest duration and the largest positive lag into the layer. Holidays are listed from the start until the working days reach three times that bound at the end of a year, and for one year more.

Complexity: with T tasks and L links, L grows in proportion to T. Building the network and writing the files takes O(T log T) time, from sorting the links and UIDs, plus time in proportion to the number of calendar years.

Options considered:

- Random pairs of tasks with a cycle check after each link. It needs a graph search per link, and the depth of the network is hard to control.
- Layers inside phases (chosen). Forward links cannot form a cycle, and the schedule length stays in years at the task limit.
- Write Start and Finish dates. This needs a scheduling engine in the generator. Left out, so a reader computes the dates.
- Ranges in working minutes. Percent keeps a row valid when a plan duration is edited (chosen: percent).
- A project library for the XML. It adds a dependency. The standard library is enough for the elements used.

## Consequences

`synthbiz check` does not read project folders. Phases run mostly in series. Durations, costs, ranges, probabilities and groups are made up and not real-world statistics. The calendar bound covers the plan with a margin, but a long enough simulated delay can pass the last listed holiday. `generate --force` does not check the kind of an existing manifest.json.
