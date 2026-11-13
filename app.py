import os
import sqlite3
from datetime import datetime

import requests
from flask import Flask, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "chave-local")
BANCO = os.environ.get("DATABASE_PATH", "banco.db")

# a API devolve um número para a condição do tempo, aqui traduzo para texto
codigos_clima = {
    0: "Céu limpo", 1: "Quase limpo", 2: "Parcialmente nublado", 3: "Nublado",
    45: "Neblina", 48: "Neblina", 51: "Garoa fraca", 53: "Garoa", 55: "Garoa forte",
    61: "Chuva fraca", 63: "Chuva", 65: "Chuva forte", 80: "Pancadas de chuva",
    81: "Pancadas de chuva", 82: "Pancadas fortes", 95: "Tempestade",
}


def conectar():
    conexao = sqlite3.connect(BANCO)
    # permite pegar a coluna pelo nome (linha["cidade"]) em vez da posição
    conexao.row_factory = sqlite3.Row
    return conexao


def criar_tabelas():
    conexao = conectar()
    conexao.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL
        )
    """)
    conexao.execute("""
        CREATE TABLE IF NOT EXISTS consultas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            cidade TEXT NOT NULL,
            pais TEXT,
            temperatura REAL,
            umidade INTEGER,
            vento REAL,
            condicao TEXT,
            data_hora TEXT NOT NULL,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    """)
    conexao.commit()
    conexao.close()


def buscar_clima(nome_cidade):
    # primeira chamada: descobre a latitude e longitude da cidade
    resposta = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": nome_cidade, "count": 1, "language": "pt"},
        timeout=10,
    )
    dados = resposta.json()
    if "results" not in dados:
        return None
    local = dados["results"][0]

    # segunda chamada: com a latitude e longitude, pega o clima atual
    resposta = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": local["latitude"],
            "longitude": local["longitude"],
            "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
            "timezone": "auto",
        },
        timeout=10,
    )
    atual = resposta.json()["current"]

    return {
        "cidade": local["name"],
        "pais": local.get("country", ""),
        "temperatura": atual["temperature_2m"],
        "umidade": atual["relative_humidity_2m"],
        "vento": atual["wind_speed_10m"],
        "condicao": codigos_clima.get(atual["weather_code"], "Indefinido"),
    }


def ultimas_consultas(usuario_id):
    conexao = conectar()
    linhas = conexao.execute(
        "SELECT * FROM consultas WHERE usuario_id = ? ORDER BY id DESC LIMIT 5",
        (usuario_id,),
    ).fetchall()
    conexao.close()
    return linhas


@app.route("/")
def index():
    if "usuario_id" in session:
        return redirect(url_for("inicio"))
    return redirect(url_for("login"))


@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        nome = request.form["nome"].strip()
        email = request.form["email"].strip().lower()
        senha = request.form["senha"]

        if nome == "" or email == "" or len(senha) < 6:
            flash("Preencha tudo e use uma senha com 6 ou mais caracteres.", "erro")
            return render_template("cadastro.html")

        conexao = conectar()
        try:
            # os ? evitam SQL injection, o sqlite coloca os valores no lugar
            # a senha nunca é salva pura, só o hash dela
            conexao.execute(
                "INSERT INTO usuarios (nome, email, senha_hash) VALUES (?, ?, ?)",
                (nome, email, generate_password_hash(senha)),
            )
            conexao.commit()
        except sqlite3.IntegrityError:
            # cai aqui quando o e-mail já existe (a coluna é UNIQUE)
            conexao.close()
            flash("Esse e-mail já está cadastrado.", "erro")
            return render_template("cadastro.html")

        conexao.close()
        flash("Conta criada! Faça login.", "ok")
        return redirect(url_for("login"))

    return render_template("cadastro.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        senha = request.form["senha"]

        conexao = conectar()
        usuario = conexao.execute(
            "SELECT * FROM usuarios WHERE email = ?", (email,)
        ).fetchone()
        conexao.close()

        # compara a senha digitada com o hash salvo no banco
        if usuario is not None and check_password_hash(usuario["senha_hash"], senha):
            # session guarda os dados do usuário logado entre uma página e outra
            session["usuario_id"] = usuario["id"]
            session["usuario_nome"] = usuario["nome"]
            return redirect(url_for("inicio"))

        flash("E-mail ou senha incorretos.", "erro")

    return render_template("login.html")


@app.route("/sair")
def sair():
    session.clear()
    return redirect(url_for("login"))


@app.route("/inicio", methods=["GET", "POST"])
def inicio():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    resultado = None

    if request.method == "POST":
        cidade = request.form["cidade"].strip()

        try:
            resultado = buscar_clima(cidade)
        except requests.exceptions.RequestException:
            flash("Não consegui acessar a API agora. Tente de novo.", "erro")
            return render_template("inicio.html", resultado=None,
                                   recentes=ultimas_consultas(session["usuario_id"]))

        if resultado is None:
            flash("Cidade não encontrada.", "erro")
        else:
            conexao = conectar()
            conexao.execute(
                """INSERT INTO consultas
                   (usuario_id, cidade, pais, temperatura, umidade, vento, condicao, data_hora)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (session["usuario_id"], resultado["cidade"], resultado["pais"],
                 resultado["temperatura"], resultado["umidade"], resultado["vento"],
                 resultado["condicao"], datetime.now().strftime("%d/%m/%Y %H:%M")),
            )
            conexao.commit()
            conexao.close()

    recentes = ultimas_consultas(session["usuario_id"])
    return render_template("inicio.html", resultado=resultado, recentes=recentes)


@app.route("/relatorio")
def relatorio():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    conexao = conectar()
    consultas = conexao.execute(
        "SELECT * FROM consultas WHERE usuario_id = ? ORDER BY id DESC",
        (session["usuario_id"],),
    ).fetchall()
    conexao.close()

    media = 0
    if len(consultas) > 0:
        soma = 0
        for c in consultas:
            soma += c["temperatura"]
        media = soma / len(consultas)

    emitido = datetime.now().strftime("%d/%m/%Y %H:%M")
    return render_template("relatorio.html", consultas=consultas, media=media, emitido=emitido)


# fica fora do if abaixo para o gunicorn (no Render) também criar as tabelas
criar_tabelas()

if __name__ == "__main__":
    app.run(debug=True)
