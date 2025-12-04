# Solution

Note: The complete solution is hosted in GCP.

## Workflow
The following image shows the high level workflow of the solution to the usecase:
![Workflow](images/Rearc-flow.png)

## Summary
The overall solution is divided into two main folders:
- cloud_run_functions
- part_3

Given the requirement to auto trigger the generation of report using part 1 and part 2 
sections of the data, all the parts except the ipynb notebook is added to the cloud_run_functions
folder. Folder part_3 contains the ipynb notebook having the required code for solving the queries 
of part 3.

To keep the solution simple yet approachable for further refinement/ upgrades, I decided to move
with pandas for part 3 of the Quest. Ideally, the solution could be implemented via views in BigQuery
as well. Can spark be used? Yes, it can be. But, it would be an overkill for the usecase at hand.
And, the solution still can be BigQuery centric if external tables are to be used with an exception
that the data from Datausa's Honolulu api would need to be massaged to get the relevant portion in GCS
itself.

There are two main handler files inside cloud_run_functions folder:
- http_handler.py
    Exposes two flask endpoints. One to ingest the BLS data and other for Datausa Honolulu data.
- event_handler.py
    Exposes one flask endpoint to handle the trigger coming in via eventarc.

Eventarc was chosen to be used as this becomes a central service for all sorts of async trigger mechanisms
instead of handling multiple heterogenours mechanisms.
The only drawback of this mechanism (which GCP is still improving) is multiple trigger at certain random 
times in case ack is delayed by the receiving party. But, this solution will scale no matter the traffic 
in case multiple workflows were to come into the picture. Also, it used PubSub internally for required 
message transfer further cementing scalability queries just like SQS/SNS in AWS.

Given it's GCP, I took the liberty to use Cloud Run Functions compared to Lambda in AWS. This also needed
a Docker image to encapsulate the complete solution. I have developed the image with most basic layers possible.
The good thing about this scenario is that the environment in the container is moldable to the requirement at 
hand also paving a way for complex installments for any API in the given future.




Now, given the priorities and time at hand, I have taken the liberty to compress the files into one folder.
Refinements can be done if this was to be fully productionalized.

