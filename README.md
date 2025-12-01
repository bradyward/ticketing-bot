# Ticketing Bot
This bot creates tickets for lead cold calling. Leads are stored in a remote database. 

The database has 2 tables: new_leads and old_leads. Both store the lead's business_name, city, and phone_number (unique). When leads are retrieved, they move to old leads and will not appear again. All incoming leads are checked against old_leads before adding to new_leads.

### Features
When a new user joins the discord, they have access to *entry* and can open an application ticket. A member of *ticket_staff* can approve or deny the ticket. An approved user gains the *caller* role.

A *caller* can view the *leads* channel and can click the "Get Leads" button. Doing so opens a ticket under the *tickets* channel category only visible to them and *ticket_staff*. When a ticket is closed by the user, a notification is sent to *daily_reports*.

### Commands
!setup -> confirmsetup  | Creates all necessary channels and roles. Currently deletes and remakes everything. Password confirmation will be removed when this doesn't delete the channels and roles 

### TODO
- Fix bot to resume working if restarted in the terminal. Currently, it loses track of all channels it created. Fix is to point it to the channel ID's that we store in the .env file upon creating it.
- When a user opens an application, auto-redirect them to the application channel
- Ensure lead order retrieval is not handled by the bot and it always grabs the top X leads
- Prevent duplicate applications from the same user
- Implement a tracking system for users who book appointments
- Fix application message content
- Fix ticket lead format
- Move applications to the 'applications' category and keep lead tickets in the 'tickets' category
- Stop notifications
- Update daily reports to list out the number of closed tickets per caller
- Ban users with denied applications
- Move parameters from in-line in bot.py to a config file (or .env file)
