from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import timedelta
import pandas as pd
import io
import requests
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)
db = SQLAlchemy(app)

class InjuryReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    datetime = db.Column(db.String(20), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    actions = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<InjuryReport {self.id} - {self.name}>'

admins = {
    "UKGP": "UKGP_PASS"
}

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        if username in admins and admins[username] == password:
            session.permanent = True
            session['admin'] = username
            flash('Вы успешно вошли как администратор!', 'success')
            return redirect(url_for('report'))
        else:
            flash('Неверный логин или пароль', 'danger')
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop('admin', None)
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('login'))

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        name = request.form['name']
        datetime = request.form['datetime']
        location = request.form['location']
        description = request.form['description']
        actions = request.form.get('actions', '')

        new_report = InjuryReport(
            name=name,
            datetime=datetime,
            location=location,
            description=description,
            actions=actions
        )
        db.session.add(new_report)
        db.session.commit()

        return redirect(url_for('index'))
    return render_template("index.html")

@app.route("/report", methods=["GET", "POST"])
def report():
    if 'admin' not in session:
        flash('Вы должны быть администратором для просмотра отчетов.', 'danger')
        return redirect(url_for('login'))
    
    name_filter = request.args.get('name')
    location_filter = request.args.get('location')
    date_filter = request.args.get('datetime')

    query = InjuryReport.query

    if name_filter:
        query = query.filter(InjuryReport.name.ilike(f'%{name_filter}%'))
    if location_filter:
        query = query.filter(InjuryReport.location.ilike(f'%{location_filter}%'))
    if date_filter:
        query = query.filter(InjuryReport.datetime == date_filter)

    reports = query.all()

    return render_template("report.html", reports=reports)

@app.route("/delete/<int:id>", methods=["POST"])
def delete_report(id):
    if 'admin' not in session:
        flash('Только администраторы могут удалять отчеты.', 'danger')
        return redirect(url_for('login'))
    
    report_to_delete = InjuryReport.query.get_or_404(id)
    try:
        db.session.delete(report_to_delete)
        db.session.commit()
        flash(f'Отчет {id} удален', 'success')
        return redirect(url_for('report'))
    except Exception as e:
        db.session.rollback()
        flash('Ошибка при удалении отчета', 'danger')
        return redirect(url_for('report'))

@app.route("/export")
def export_reports():
    if 'admin' not in session:
        flash('Только администраторы могут экспортировать отчеты.', 'danger')
        return redirect(url_for('login'))
    
    reports = InjuryReport.query.all()
    data = [
        {
            "ID": report.id,
            "Имя сотрудника": report.name,
            "Дата": report.datetime,
            "Место": report.location,
            "Описание": report.description,
            "Действия": report.actions
        }
        for report in reports
    ]
    
    df = pd.DataFrame(data)
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    
    output.seek(0)
    
    return send_file(output, as_attachment=True, download_name='injury_reports.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route("/statistics")
def statistics():
    if 'admin' not in session:
        flash('Только администраторы могут просматривать статистику.', 'danger')
        return redirect(url_for('login'))
    
    reports = InjuryReport.query.all()
    
    injury_types = {}
    locations = {}
    workers = {}
    
    for report in reports:
        injury_types[report.description] = injury_types.get(report.description, 0) + 1
        
        locations[report.location] = locations.get(report.location, 0) + 1
        
        workers[report.name] = workers.get(report.name, 0) + 1
    
    return render_template("statistics.html", injury_types=injury_types, locations=locations, workers=workers)

@app.route('/chat', methods=['POST', 'GET'])
def chat():
    if request.method == "POST":
        data = request.get_json()

        prompt = {
        "role": "system",
        "content": "Пожалуйста, отвечайте только на вопросы, связанные с медициной."
        }

        if 'request' in data and 'messages' in data['request']:
            data['request']['messages'].insert(0, prompt)

        onlysq_url = 'http://api.onlysq.ru/ai/v2'

        try:
            response = requests.post(onlysq_url, json=data)
            response_data = response.json()

            return jsonify(response_data), response.status_code
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        return render_template("chat.html")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    
    app.run(host="0.0.0.0",debug=True)
  
