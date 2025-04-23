from flask import Flask, render_template, request, redirect, url_for, flash 
from flask_sqlalchemy import SQLAlchemy 
from flask_login import ( 
    LoginManager, 
    UserMixin, 
    login_user, 
    login_required, 
    logout_user, 
    current_user 
) 
from datetime import datetime 
import re 
import tempfile
import os
import subprocess
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__, template_folder="templates") 

# Configuration
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "your-secret-key")
# Use PostgreSQL in production, SQLite in development
if os.getenv("DATABASE_URL"):
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///orders.db"
    
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False 

# Custom flash message categories
app.config['MESSAGE_CATEGORIES'] = {
    'success': 'positive',  # Green messages
    'error': 'negative',    # Red messages
    'info': 'info',        # Blue messages
    'warning': 'warning'    # Yellow messages
}

db = SQLAlchemy(app) 

# Setup Flask-Login 
login_manager = LoginManager(app) 
login_manager.login_view = "login" 

######################################## 
# Database Models 
######################################## 
class User(db.Model, UserMixin): 
    id = db.Column(db.Integer, primary_key=True) 
    username = db.Column(db.String(50), unique=True, nullable=False)  # Auto-populated from selected Site. 
    email = db.Column(db.String(120), nullable=False) 
    password = db.Column(db.String(50), nullable=False)  # For demo purposes only. 
    role = db.Column(db.String(20), nullable=False)  # "Admin" or "Manager" 
    def __repr__(self): 
        return f"<User {self.username} - {self.role}>" 

class Order(db.Model): 
    id = db.Column(db.Integer, primary_key=True) 
    supplier = db.Column(db.String(100), nullable=False) 
    description = db.Column(db.String(500), nullable=False) 
    amount = db.Column(db.Float, nullable=False)  # Total Amount field (Incl.)
    submitter = db.Column(db.String(50), nullable=False)  # Holds the Site selected. 
    created_at = db.Column(db.DateTime, default=datetime.now) 
    status = db.Column(db.String(20), default="pending") 
    approver = db.Column(db.String(50)) 
    approved_at = db.Column(db.DateTime, nullable=True) 
    submitter_emp_number = db.Column(db.String(20), nullable=True) 
    submitter_emp_name = db.Column(db.String(100), nullable=True) 
    approver_emp_number = db.Column(db.String(20), nullable=True) 
    approver_emp_name = db.Column(db.String(100), nullable=True) 
    def __repr__(self): 
        return f"<Order {self.id} - {self.status}>" 

######################################## 
# Outlook Email Helper Using COM 
######################################## 
def send_email_via_outlook(recipient, subject, body, sender=None): 
    try: 
        import pythoncom 
        pythoncom.CoInitialize() 
        import win32com.client as win32 
        outlook = win32.Dispatch('Outlook.Application') 
        mail = outlook.CreateItem(0)  # 0: Outlook mail item. 
        mail.To = recipient 
        mail.Subject = subject 
        mail.Body = body 
        if sender and sender.lower() != recipient.lower(): 
            mail.SentOnBehalfOfName = sender 
        print(f"Attempting to send email to {recipient} with subject '{subject}'...") 
        mail.Send() 
        print(f"Email successfully sent to {recipient} with subject '{subject}'") 
        pythoncom.CoUninitialize() 
    except Exception as e: 
        print("Error sending email:", e) 

######################################## 
# User Loader for Flask-Login 
######################################## 
@login_manager.user_loader 
def load_user(user_id): 
    return User.query.get(int(user_id)) 

######################################## 
# Routes 
######################################## 
@app.route("/") 
@login_required 
def index(): 
    orders = Order.query.order_by(Order.created_at.desc()).all() 
    # Attach the submitter's role to each order for approval button logic. 
    for order in orders: 
        user = User.query.filter_by(username=order.submitter).first() 
        if user: 
            order.submitter_role = user.role 
        else: 
            order.submitter_role = "Unknown" 
    return render_template("index.html", orders=orders) 

@app.route("/login", methods=["GET", "POST"]) 
def login(): 
    if current_user.is_authenticated: 
        return redirect(url_for("index")) 
    if request.method == "POST": 
        username = request.form.get("username") 
        password = request.form.get("password") 
        user = User.query.filter_by(username=username).first() 
        if user and user.password == password: 
            login_user(user) 
            flash("Welcome back! You have successfully logged in.", "success") 
            return redirect(url_for("index")) 
        else: 
            flash("Invalid username or password. Please try again.", "error") 
    return render_template("login.html") 

@app.route("/logout") 
@login_required 
def logout(): 
    logout_user() 
    flash("You have been successfully logged out. Have a great day!", "success") 
    return redirect(url_for("login")) 

# Registration Route 
@app.route("/register", methods=["GET", "POST"]) 
def register(): 
    sites = { 
        "TWT Alberton": "TWT Alberton",
        "TWT Amanzimtoti": "TWT Amanzimtoti",
        "TWT Balfour Park": "TWT Balfour Park",
        "TWT Bedfordview": "TWT Bedfordview",
        "TWT Bellville": "TWT Bellville",
        "TWT Benoni": "TWT Benoni",
        "TWT Boksburg": "TWT Boksburg",
        "TWT Brits": "TWT Brits",
        "TWT Broadacres": "TWT Broadacres",
        "TWT Canal Walk": "TWT Canal Walk",
        "TWT Cape Gate": "TWT Cape Gate",
        "TWT Cape Town": "TWT Cape Town",
        "TWT Centurion": "TWT Centurion",
        "TWT Centurion Lifestyle": "TWT Centurion Lifestyle",
        "TWT Claremont": "TWT Claremont",
        "TWT Cradlestone": "TWT Cradlestone",
        "TWT Cresta": "TWT Cresta",
        "TWT Durban": "TWT Durban",
        "TWT Durbanville": "TWT Durbanville",
        "TWT Eastgate": "TWT Eastgate",
        "TWT Festival Mall": "TWT Festival Mall",
        "TWT Fordsburg": "TWT Fordsburg",
        "TWT Fourways": "TWT Fourways",
        "TWT George": "TWT George",
        "TWT Gezina": "TWT Gezina",
        "TWT Greenstone": "TWT Greenstone",
        "TWT Groblersdal": "TWT Groblersdal",
        "TWT Hammanskraal": "TWT Hammanskraal",
        "TWT Hatfield": "TWT Hatfield",
        "TWT Kempton Park": "TWT Kempton Park",
        "TWT Keywest": "TWT Keywest",
        "TWT Killarney Mall": "TWT Killarney Mall",
        "TWT Klerksdorp": "TWT Klerksdorp",
        "TWT La Lucia": "TWT La Lucia",
        "TWT Lephalale": "TWT Lephalale",
        "TWT Lynnwood": "TWT Lynnwood",
        "TWT Mall at Reds": "TWT Mall at Reds",
        "TWT Meadowdale": "TWT Meadowdale",
        "TWT Melrose": "TWT Melrose",
        "TWT Menlyn": "TWT Menlyn",
        "TWT Middelburg": "TWT Middelburg",
        "TWT Midrand": "TWT Midrand",
        "TWT Modimolle": "TWT Modimolle",
        "TWT Mokopane": "TWT Mokopane",
        "TWT Montana": "TWT Montana",
        "TWT Mosselbay": "TWT Mosselbay",
        "TWT Mt Edgecombe": "TWT Mt Edgecombe",
        "TWT Musina": "TWT Musina",
        "TWT N1 City": "TWT N1 City",
        "TWT Nelspruit CBD": "TWT Nelspruit CBD",
        "TWT Newmarket": "TWT Newmarket",
        "TWT Noordhoek": "TWT Noordhoek",
        "TWT Paarl": "TWT Paarl",
        "TWT Paarl Mall": "TWT Paarl Mall",
        "TWT Parkdene": "TWT Parkdene",
        "TWT Parklands": "TWT Parklands",
        "TWT PE Heugh Road": "TWT PE Heugh Road",
        "TWT Pinetown": "TWT Pinetown",
        "TWT Polokwane": "TWT Polokwane",
        "TWT Port Elizabeth": "TWT Port Elizabeth",
        "TWT Potchefstroom": "TWT Potchefstroom",
        "TWT Pretoria CBD": "TWT Pretoria CBD",
        "TWT Randburg": "TWT Randburg",
        "TWT Randfontein": "TWT Randfontein",
        "TWT Raslouw": "TWT Raslouw",
        "TWT Riverside": "TWT Riverside",
        "TWT Rivonia": "TWT Rivonia",
        "TWT Rosebank": "TWT Rosebank",
        "TWT Rustenburg": "TWT Rustenburg",
        "TWT Sandhurst": "TWT Sandhurst",
        "TWT Sandton": "TWT Sandton",
        "TWT Savannah": "TWT Savannah",
        "TWT Silverlakes": "TWT Silverlakes",
        "TWT Somerset": "TWT Somerset",
        "TWT Springfield": "TWT Springfield",
        "TWT Springs": "TWT Springs",
        "TWT Stellenbosch": "TWT Stellenbosch",
        "TWT Strijdom Park": "TWT Strijdom Park",
        "TWT Strubens Valley": "TWT Strubens Valley",
        "TWT Sunninghill": "TWT Sunninghill",
        "TWT Tableview": "TWT Tableview",
        "TWT Tembisa": "TWT Tembisa",
        "TWT The Glen": "TWT The Glen",
        "TWT Tokai": "TWT Tokai",
        "TWT Tygervalley": "TWT Tygervalley",
        "TWT Umhlanga": "TWT Umhlanga",
        "TWT Vanderbijlpark": "TWT Vanderbijlpark",
        "TWT Walmer": "TWT Walmer",
        "TWT Westgate": "TWT Westgate",
        "TWT Wonderboom": "TWT Wonderboom",
        "TWT Wonderpark": "TWT Wonderpark",
        "TWT Woodlands Mall": "TWT Woodlands Mall",
        "TWT Woodmead": "TWT Woodmead"
    } 
    roles = { 
        "Admin": "Admin", 
        "Manager": "Manager" 
    } 
    if request.method == "POST": 
        site = request.form.get("site") 
        selected_role = request.form.get("role") 
        email = request.form.get("email") 
        password = request.form.get("password") 
        
        # Improved validation messages
        if site not in sites: 
            flash("Please select a valid Tiger Wheel & Tyre site from the list.", "error") 
            return render_template("register.html", sites=sites, roles=roles) 
        if selected_role not in roles: 
            flash("Please select either Admin or Manager role.", "error") 
            return render_template("register.html", sites=sites, roles=roles) 
        if not email or "@" not in email: 
            flash("Please provide a valid email address (e.g., name@company.com).", "error") 
            return render_template("register.html", sites=sites, roles=roles) 
        
        # Password validation with clearer messages
        password_errors = []
        if len(password) < 8:
            password_errors.append("at least 8 characters")
        if not re.search(r'[A-Z]', password):
            password_errors.append("one uppercase letter")
        if not re.search(r'\d', password):
            password_errors.append("one number")
        if not re.search(r'[\W_]', password):
            password_errors.append("one special character")
            
        if password_errors:
            flash(f"Password must contain {', '.join(password_errors)}.", "error")
            return render_template("register.html", sites=sites, roles=roles)

        username = site  # Username is derived from the selected site. 
        if User.query.filter_by(username=username).first(): 
            flash("An account for this site already exists. Please log in.", "danger") 
            return redirect(url_for("login")) 
        new_user = User(username=username, email=email, password=password, role=selected_role) 
        db.session.add(new_user) 
        db.session.commit() 
        flash("Account created successfully! Please log in.", "success") 
        return redirect(url_for("login")) 
    return render_template("register.html", sites=sites, roles=roles) 

# Create Order Route with Submitter Employee Details and new Item Details 
@app.route("/create", methods=["GET", "POST"]) 
@login_required 
def create_order():
    if request.method == "POST":
        supplier = request.form.get("supplier", "").strip()
        if not supplier:
            flash("Supplier is required.", "danger")
            return render_template("create_order.html")
        
        # Gather item details arrays from the new item table. 
        item_descs = request.form.getlist("item_desc[]")
        item_qtys = request.form.getlist("item_qty[]")
        item_unit_costs = request.form.getlist("item_unit_cost[]")
        item_total_costs = request.form.getlist("item_total_cost[]")
        
        # Validate that at least one item description is provided.
        if not item_descs or all(d.strip() == "" for d in item_descs):
            flash("At least one item description is required.", "danger")
            return render_template("create_order.html")
        
        # Combine each row's data into one description string.
        description_lines = []
        for i in range(len(item_descs)):
            qty = item_qtys[i].strip() if i < len(item_qtys) else ""
            desc = item_descs[i].strip()
            unit_cost = item_unit_costs[i].strip() if i < len(item_unit_costs) else ""
            total_cost = item_total_costs[i].strip() if i < len(item_total_costs) else ""
            if desc != "":
                line = f"QTY: {qty}, Description: {desc}, Unit Cost Excl.: {unit_cost}, Total Unit Cost Excl.: {total_cost}"
                description_lines.append(line)
        description = "\n".join(description_lines)
        
        # Get the total amount incl. from the summary field.
        amount_str = request.form.get("amount", "").strip()
        if not amount_str:
            flash("Total Amount Incl. is required.", "danger")
            return render_template("create_order.html")
        try:
            amount = float(amount_str)
        except ValueError:
            flash("Please enter a valid number for the Total Amount Incl.", "danger")
            return render_template("create_order.html")
            
        submitter_emp_number = request.form.get("submitter_emp_number")
        submitter_emp_name = request.form.get("submitter_emp_name")
        if not submitter_emp_number or not submitter_emp_name:
            flash("Employee Number and Employee Name are required for submission.", "danger")
            return render_template("create_order.html")
        
        new_order = Order(
            supplier=supplier,
            description=description,
            amount=amount,
            submitter=current_user.username,
            submitter_emp_number=submitter_emp_number,
            submitter_emp_name=submitter_emp_name
        )
        db.session.add(new_order)
        db.session.commit()
        flash("Order created successfully!", "success")
        # Email notification to the opposing role. 
        if current_user.role == "Admin":
            subject = "New Order Awaiting Approval"
            body = (
                f"Dear Manager,\n\n"
                f"A new order created by {current_user.username} (Admin) is awaiting your approval.\n"
                f"Order ID: {new_order.id}\n"
                f"Supplier: {new_order.supplier}\n"
                f"Description:\n{new_order.description}\n"
                f"Total Amount Incl.: {new_order.amount:.2f}\n"
                f"Submitter (Emp #, Name): {new_order.submitter_emp_number}, {new_order.submitter_emp_name}\n\n"
                "Please log in to review and approve the order."
            )
            send_email_via_outlook(recipient="deand@twt.to", subject=subject, body=body, sender="deand@twt.to")
        elif current_user.role == "Manager":
            subject = "New Order Awaiting Approval"
            body = (
                f"Dear Admin,\n\n"
                f"A new order created by {current_user.username} (Manager) is awaiting your approval.\n"
                f"Order ID: {new_order.id}\n"
                f"Supplier: {new_order.supplier}\n"
                f"Description:\n{new_order.description}\n"
                f"Total Amount Incl.: {new_order.amount:.2f}\n"
                f"Submitter (Emp #, Name): {new_order.submitter_emp_number}, {new_order.submitter_emp_name}\n\n"
                "Please log in to review and approve the order."
            )
            send_email_via_outlook(recipient="deand@twt.to", subject=subject, body=body, sender="deand@twt.to")
        flash("Notification sent for approval.", "info")
        return redirect(url_for("index"))
    return render_template("create_order.html")

# Approve Order Route with Role Check Based on Submitter's Role 
@app.route("/approve/<int:order_id>", methods=["POST"]) 
@login_required 
def approve_order(order_id): 
    order = Order.query.get_or_404(order_id) 
    if order.status != "pending": 
        flash("This order has already been processed.", "warning") 
        return redirect(url_for("index")) 
    submitter_obj = User.query.filter_by(username=order.submitter).first() 
    if not submitter_obj: 
        flash("Submitter account not found.", "danger") 
        return redirect(url_for("index")) 
    # Allow approval only if the current user's role is the opposite of the submitter's. 
    if (submitter_obj.role == "Admin" and current_user.role == "Manager") or \
       (submitter_obj.role == "Manager" and current_user.role == "Admin"): 
        approver_emp_number = request.form.get("approver_emp_number") 
        approver_emp_name = request.form.get("approver_emp_name") 
        if not approver_emp_number or not approver_emp_name: 
            flash("Employee Number and Employee Name are required for approval.", "danger") 
            return redirect(url_for("index")) 
        order.status = "approved" 
        order.approver = current_user.username 
        order.approved_at = datetime.now() 
        order.approver_emp_number = approver_emp_number 
        order.approver_emp_name = approver_emp_name 
        db.session.commit() 
        flash(f"Order #{order.id} has been successfully approved.", "success") 
        subject = "Your Order Has Been Approved" 
        if submitter_obj.role == "Admin": 
            body = ( 
                f"Dear Admin,\n\n" 
                f"Your order (ID: {order.id}) has been approved by the Manager ({current_user.username}).\n" 
                f"Approver (Emp #, Name): {order.approver_emp_number}, {order.approver_emp_name}\n" 
                "You can now proceed to print the order.\n\n" 
                "Best regards,\nOrder Management System" 
            ) 
        else: 
            body = ( 
                f"Dear Manager,\n\n" 
                f"Your order (ID: {order.id}) has been approved by the Admin ({current_user.username}).\n" 
                f"Approver (Emp #, Name): {order.approver_emp_number}, {order.approver_emp_name}\n" 
                "You can now proceed to print the order.\n\n" 
                "Best regards,\nOrder Management System" 
            ) 
        send_email_via_outlook(recipient="deand@twt.to", subject=subject, body=body, sender="deand@twt.to") 
        flash("Notification sent regarding approval.", "info") 
    else: 
        flash("You are not authorized to approve this order.", "danger") 
    return redirect(url_for("index")) 

# Decline Order Route with Role Check 
@app.route("/decline/<int:order_id>", methods=["POST"])
@login_required
def decline_order(order_id):
    order = Order.query.get_or_404(order_id)
    if order.status != "pending": 
        flash("This order has already been processed.", "warning") 
        return redirect(url_for("index")) 
    submitter_obj = User.query.filter_by(username=order.submitter).first()
    if not submitter_obj:
        flash("Submitter account not found.", "danger")
        return redirect(url_for("index"))
    if (submitter_obj.role == "Admin" and current_user.role == "Manager") or \
       (submitter_obj.role == "Manager" and current_user.role == "Admin"):
        approver_emp_number = request.form.get("approver_emp_number")
        approver_emp_name = request.form.get("approver_emp_name")
        if not approver_emp_number or not approver_emp_name:
            flash("Employee Number and Employee Name are required for decline.", "danger")
            return redirect(url_for("index"))
        order.status = "declined"
        order.approver = current_user.username
        order.approved_at = datetime.now()
        order.approver_emp_number = approver_emp_number
        order.approver_emp_name = approver_emp_name
        db.session.commit()
        flash(f"Order #{order.id} has been declined.", "error")
        subject = "Your Order Has Been Declined"
        body = (
            f"Dear {submitter_obj.username},\n\n"
            f"Your order (ID: {order.id}) has been declined by {current_user.username}.\n"
            f"Decliner (Emp #, Name): {order.approver_emp_number}, {order.approver_emp_name}\n\n"
            "Please contact your approver for more information."
        )
        send_email_via_outlook(recipient="deand@twt.to", subject=subject, body=body, sender="deand@twt.to")
    else:
        flash("You are not authorized to decline this order.", "danger")
    return redirect(url_for("index"))

@app.route("/print/<int:order_id>") 
@login_required 
def print_order(order_id): 
    order = Order.query.get_or_404(order_id) 
    return render_template("print_order.html", order=order) 

# Send to Supplier Route using Headless Chromium to generate PDF
@app.route("/send_to_supplier/<int:order_id>")
@login_required
def send_to_supplier(order_id):
    order = Order.query.get_or_404(order_id)
    
    # Render the print_order template to HTML string
    rendered = render_template("print_order.html", order=order)
    
    # Write the HTML to a temporary file
    temp_html = tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8")
    temp_html.write(rendered)
    temp_html.close()
    
    # Create a temporary file for the PDF
    temp_pdf = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
    temp_pdf.close()
    
    # Path to Chrome executable - update this path according to your system
    chrome_executable_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    
    try:
        # Build the command to run headless Chrome
        command = [
            chrome_executable_path,
            "--headless",
            "--disable-gpu",
            f"--print-to-pdf={temp_pdf.name}",
            "file:///" + temp_html.name
        ]
        
        # Generate PDF using headless Chrome
        subprocess.run(command, check=True)
        
        # Initialize COM for Outlook
        import pythoncom
        pythoncom.CoInitialize()
        import win32com.client as win32
        
        # Create and display Outlook email with PDF attachment
        outlook = win32.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)  # 0: Outlook mail item
        mail.Subject = f"Order #{order.id} from Tiger Wheel & Tyre {order.submitter}"
        
        # Create professional email body
        mail.Body = f"""Dear Supplier,

Please find attached the order details from Tiger Wheel & Tyre {order.submitter}.

Order Details:
-------------
Order ID: {order.id}
Site: {order.submitter}
Status: {order.status.upper()}
Created: {order.created_at.strftime('%Y-%m-%d %H:%M:%S')}

Total Amount (Excl. VAT): R{order.amount / 1.155:.2f}
VAT (15.5%): R{order.amount - (order.amount / 1.155):.2f}
Total Amount (Incl. VAT): R{order.amount:.2f}

Submitted by: {order.submitter_emp_name} ({order.submitter_emp_number})
{f"Approved by: {order.approver_emp_name} ({order.approver_emp_number})" if order.status == "approved" else ""}

Best regards,
Tiger Wheel & Tyre Team"""

        # Attach the PDF
        mail.Attachments.Add(temp_pdf.name)
        
        # Display the email (but don't send it automatically)
        mail.Display(False)
        
        pythoncom.CoUninitialize()
        flash(f"Order #{order.id} has been prepared for sending to supplier. Please review and send the email.", "success")
        
    except Exception as e:
        flash(f"Error preparing supplier email: {str(e)}", "error")
        
    finally:
        # Clean up temporary files
        try:
            os.unlink(temp_html.name)
            os.unlink(temp_pdf.name)
        except:
            pass  # Ignore cleanup errors
    
    return redirect(url_for("print_order", order_id=order_id))

def setup_users():
    admin = User.query.filter_by(username="Admin").first()
    if not admin:
        admin = User(username="Admin", email="deand@twt.to", password="Admin", role="Admin")
        db.session.add(admin)
    manager = User.query.filter_by(username="Manager").first()
    if not manager:
        # Use a unique email address for the Manager.
        manager = User(username="Manager", email="manager@twt.to", password="Manager", role="Manager")
        db.session.add(manager)
    db.session.commit()

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        setup_users()
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)))