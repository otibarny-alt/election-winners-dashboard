2027 ALL-ELECTIONS WINNERS & RUNNERS-UP DASHBOARD V1

PURPOSE
Combines President, Governor, Senator, Woman Rep, MNA and MCA Kobo result projects.

CURRENT LEADERS
The drill-down filters are:
National -> County -> Constituency -> Ward -> Polling Station -> Stream.

The six contest cards show the current leader, runner-up, vote margin, reporting
percentage and top-five ranking.

To avoid mixing different candidate ballots:
- President can be calculated at any scope.
- Governor, Senator and Woman Rep require a County.
- MNA requires a Constituency.
- MCA requires a Ward.

WINNER VS LEADER
Before all expected polling-station streams in the selected scope have reported,
the card says LEADING. At 100% reporting it changes to WINNER.

WINNERS / LEADERS BOARD
The board tab creates the appropriate area-level comparison:
- President: national/current selected scope
- Governor: every county
- Senator: every county
- Woman Rep: every county
- MNA: every constituency
- MCA: every ward

Each row shows leader/winner, runner-up, votes, margin and reporting status.

DEPLOYMENT
Use a separate GitHub repository and separate Render Web Service.
Build command: pip install -r requirements.txt
Start command: gunicorn app:app
Set all variables shown in .env.example.
