# E-Commerce Admin Application

A Flask-based E-Commerce administration panel for managing products. This application allows verified administrators to register, log in, and manage product inventory.

## Features

- **Admin Authentication**: Secure registration with OTP (One-Time Password) verification via Email. Login using hashed passwords.
- **Product Management**: 
  - Add new products with details like name, description, price, category, stock, and images.
  - View a list of products with search and category filtering capabilities.
  - Update product details.
  - Delete products (including automatic removal of associated images).

## Prerequisites

- Python 3.8+
- MySQL Server

## Setup Instructions

1. **Clone the repository:**
   ```bash
   git clone https://github.com/bhavanajoseph84392-png/E-Commerce-.git
   cd E-Commerce-
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables:**
   Create a `.env` file in the root directory and configure the following variables:
   ```env
   SECRET_KEY=your_secret_key
   DB_HOST=localhost
   DB_USER=root
   DB_PASSWORD=your_mysql_password
   DB_NAME=your_database_name
   SENDER_EMAIL=your_email@gmail.com
   SENDER_PASSWORD=your_app_password
   ```

5. **Database Setup:**
   Ensure you have a MySQL database running. The application requires two tables:
   - `admins`: Stores admin details (id, name, email, password, otp, otp_expiry, is_verified, profile_image).
   - `products`: Stores product details (id, name, description, price, category, stock, image).

6. **Run the Application:**
   ```bash
   python app.py
   ```
   Access the application at `http://127.0.0.1:5000`.

## Technologies Used
- **Backend Framework**: Flask
- **Database**: MySQL (via `mysql-connector-python`)
- **Security**: `bcrypt` for password hashing
- **Email/OTP**: Python `smtplib` and `email.message`

For a deeper dive into the application's design, refer to the [ARCHITECTURE.md](ARCHITECTURE.md) file.
