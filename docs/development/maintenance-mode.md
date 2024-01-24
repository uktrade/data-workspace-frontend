---
title: Enabling Maintenance Mode in Django
---

This guide will walk you through the process of enabling maintenance mode in your Django application through the admin interface.

## Enabling Maintenance Mode

1. **Access the Django Admin Interface**: Navigate to the Django Admin Interface (`/admin`).

2. **Navigate to the Maintenance Settings**: On the admin dashboard, go to the "Maintenance" section. In this section, click on "Settings".

3. **Create or Edit a `MaintenanceSettings` Object**: In the "Settings" section, you'll see a `MaintenanceSettings` object. If one does not exist, create a new one by clicking on "ADD MAINTENANCE SETTINGS".

4. **Configure the Maintenance Settings**: In the `MaintenanceSettings` form, you'll find two fields:
    - **Maintenance Text**: This is the message that will be displayed to users when maintenance mode is enabled. For example, "The service is currently unavailable. Please try again later".
    - **Maintenance Toggle**: This checkbox enables or disables maintenance mode. Check this box to enable maintenance mode.

Once these steps are completed, maintenance mode will be enabled, and users will see your maintenance message when they try to access your application.