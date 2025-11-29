# Ticketing Bot
This bot creates tickets for lead cold calling. Leads are stored in a remote database. 

### Features
When a new user joins the discord, they have access to *entry* and can open an application ticket. A member of *ticket_staff* can approve or deny the ticket. An approved user gains the *caller* role.

A *caller* can view the *leads* channel and can click the "Get Leads" button. Doing so opens a ticket under the *tickets* channel category only visible to them and *ticket_staff*. When a ticket is closed by the user, a notification is sent to *daily_reports*.

!setup -> confirmsetup creates all necessary channels and roles

### TODO
- Fix bot to resume working if restarted. Currently, it loses track of all channels it created. 
- Ensure lead order retrieval is not handled by the bot and it always grabs the top X leads
- Prevent duplicate applications from the same user
- Implement a tracking system for users who book appointments
- Fix application message content
- Fix ticket lead format
- Stop notifications
- Update daily reports to list out the number of closed tickets per caller
- Ban users with denied applications