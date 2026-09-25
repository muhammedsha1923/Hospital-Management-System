# Hospital-Management-System
Full-stack Hospital Management System built with Django &amp; MySQL. Role-based dashboards for Admins, Doctors, Receptionists &amp; Patients — appointments, medical ## CarePoint — Hospital Management System

A full-stack hospital management web application built with **Django**, **MySQL**, HTML/CSS, and JavaScript. It provides secure, role-based access for Administrators, Doctors, Receptionists, and Patients, each with a dedicated dashboard tailored to their responsibilities.

**Features**
- 🔐 Role-based authentication and permissions (Admin, Doctor, Receptionist, Patient)
- 📅 Appointment scheduling with automatic double-booking prevention
- 🩺 Medical records, diagnoses, prescriptions, and follow-up tracking
- 🛏️ Room/bed management and patient admissions with auto-generated room charges
- 💳 Billing and invoicing with live payment status (Pending / Partial / Paid)
- 📊 Real-time hospital statistics (patients, doctors, appointments, revenue)
- 📱 Responsive, professional hospital-style UI with progressive JavaScript enhancements

Built following Django's MVT architecture with cleanly separated apps (`accounts`, `doctors`, `patients`, `appointments`, `records`, `admissions`, `billing`, `dashboard`) and a full test suite covering permissions, scheduling rules, and billing logic.
