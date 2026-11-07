Answer four questions about the finding, each yes or no.

The records are JSON. Each ID in them names one record: a shipment (SH-), a customs
case (RTM-) with the list of documents it requires, or a document (DOC-) with where
it is filed. A fact about a record may use anything the JSON says about that record:
a customs case's list of required documents is part of the case, and a cleared case
means its shipment cleared customs.

grounded: Does every evidence fact say only what the records show about the record
it cites? A fact that adds anything the records don't show, or cites an ID that
names no record, makes this no.

correct: Does the finding give the reference answer's cause? Different wording is
fine. A different cause, or a cause missing part of the reference's, makes this no.
Where the reference says the records can't tell, only a finding that says so too,
with status undetermined, is yes; a finding with status cause_found is no, whatever
its words.

reasoned: If its evidence facts are true, do they establish the finding's cause, or
its conclusion that the records can't tell? The fact that decides the cause must be
among the evidence: a conclusion that follows only by elimination, from facts that
don't state it, makes this no. So do true facts that don't lead to the conclusion.

relevant: Would the recommended action resolve the reference answer's cause, or,
where the records can't tell, send the case to a person to find out? An action that
would do nothing about the cause, or would do harm, makes this no.
