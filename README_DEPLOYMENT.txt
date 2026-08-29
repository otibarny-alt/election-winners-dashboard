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


V2 LOGIN ROUTE FIX
Successful login now redirects explicitly to /dashboard.
The root URL / redirects authenticated users to /dashboard and signed-out users to /login.
An authenticated 404 also redirects safely back to /dashboard instead of showing a bare Not Found page.


V3 PRESIDENTIAL VOTE FIX
The dashboard was already detecting the Presidential submission (for example,
1/43077 streams reported), but V1/V2 only added a candidate's votes if the
candidate-name calculation was also present in the Kobo submission export.

The Presidential form does not necessarily save those calculated candidate-name
fields, so valid candidate1_votes ... candidate10_votes were being skipped.

V3 tallies candidate votes by slot independently of the candidate-name fields.
For President it uses PRESIDENT_CANDIDATE_NAMES (or CANDIDATE_NAMES) as the name
fallback. Therefore the existing Mwijabu Primary School Stream 2 submission will
contribute to the national Presidential totals.

For correct candidate names, copy the same comma-separated candidate list used
in the Presidential dashboard into Render variable PRESIDENT_CANDIDATE_NAMES.


V4 TIE STATUS
If two or more candidates have the same highest vote total at any stage of
counting, the status is TIE instead of LEADING.

- The card lists all candidates tied for the highest vote total.
- Margin is 0.
- There is no sole leader while the tie remains.
- If later submissions break the tie, status automatically returns to LEADING.
- At 100% reporting, an unresolved equal highest total remains TIE rather than
  being incorrectly labelled WINNER.
- This applies to President, Governor, Senator, Woman Rep, MNA and MCA.
