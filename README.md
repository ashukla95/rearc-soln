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
with pandas for part 3 and 4 of the Quest. Ideally, the solution could be implemented via views in BigQuery
as well. Can spark be used? Yes, it can be. But, it would be an overkill for the usecase at hand.
And, the solution still can be BigQuery centric if external tables are to be used with an exception
that the data from Datausa's Honolulu api would need to be massaged to get the relevant portion in GCS
itself.

There are two main handler files inside cloud_run_functions folder:
- http_handler.py
    - Exposes two flask endpoints. One to ingest the BLS data and other for Datausa Honolulu data.
- event_handler.py
    - Exposes one flask endpoint to handle the trigger coming in via eventarc.

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

Now, the solution has been designed to be config dependent.
I used YAML as the config structure due to it's wide spread adoption and me having slight bias towards 
its cleaner reads than JSON.

The URLS of the htt_handler have been designed to take very minimal params as input and rather read from 
the config. This has been done for two purposes: simplicity and less prone to security issues.

Now, esp for Datausa, the following can be parameterized in the API url:
- drilldowns
- cube
- locale
- measures

If done, necessary checks need to be implemented to avoid any sort of injection attacks. One idea could be then
to use config files to store relevant values and then compare input against those. These may increase latency
but is a simple yet a powerful way to validate.

The API setup for Datausa was also cross-verified by re-creating the setup here: https://honolulu-api.datausa.io/ui/?cube=acs_yg_total_population_1&drilldowns%5B0%5D=Geography.Nation.Nation&drilldowns%5B1%5D=Year&locale=en&measures%5B0%5D=Population&panel=debug

For BLS, config has been defined as per the section at hand. Now, I was dealing with PR alone. Hence, in the 
config you shall see me using "pr" key only. The idea is, if down the line you need more sections to be added,
it becomes plug and play essentially.

I chose the most simplest class design to design the modules to ingest and process BLS and Datausa's data.
But, Factory + Composition along with regular inheritance can do quite a lot of complex tasks of these exercises.



Most of the setup can be run locally as well.
The steps to do so would be as follows:
- Create your own gcs bucket in the gcp project.
- Update the relevant fields in the config.yaml file
- Start the flask server by running " python3 main.py  ".
- Note: 
    - Please do create a venv and install the libraries using requirements.txt for the above steps.
    - For testing the report associated to part 3, you can run the ipynb notebook by running the jupyter server.
        And, to test the flask endpoint for the same, kindly ensure to send a cloudevent type object with required parameters.


All of the urls to the files in the gcs are present inside ** signed_urls.txt **. These are valid for 12 hours only. In case 
a check is performed post that, send me an email and I will provide new urls to reference.


Lastly, given the priorities and time at hand, I have taken the liberty to compress certain design choices.
Refinements can be done if this was to be fully productionalized and or made more de-coupled.


