# coberturas
Cobertura de Plantões do HAOC

## 🩺 Sobre o sistema

Este é um sistema completo de **inscrição de plantões da UTI**, desenvolvido em **Streamlit** com backend em **Google Sheets**, permitindo:

- Controle individual de acesso (email + senha)  
- Inscrição segura em plantões  
- Edição completa apenas para administradores  
- Registro de logs de todas as ações  
- Exportação da escala final  
- Zero risco de sobrescrita simultânea  
- Interface simples e intuitiva para médicos  

O objetivo é substituir planilhas manuais e evitar erros, conflitos e perda de dados quando muitos usuários acessam ao mesmo tempo.

---

## 🧱 Arquitetura

```
Streamlit (frontend)
       ↓
Google Sheets (backend)
       ↓
Google Cloud Service Account (autenticação)
```

### Arquivos principais

| Arquivo | Função |
|--------|--------|
| `app.py` | Interface principal do sistema |
| `backend.py` | Conexão com Google Sheets |
| `auth.py` | Login, hashing de senha e troca de senha |
| `requirements.txt` | Dependências do projeto |

---

## 🔐 Autenticação

O sistema utiliza:

- **Email** como login  
- **Senha individual** (armazenada com hash bcrypt)  
- **Troca de senha** disponível para todos os usuários  
- **Admin** definido na aba `usuarios` do Google Sheets  

### Colunas da aba `usuarios`:

```
email | senha_hash | nome | ativo | admin
```

- `admin = TRUE` → acesso total  
- `admin = FALSE` → acesso restrito  

---

## 👑 Permissões

### **Administrador**
- Edita todos os plantões  
- Adiciona ou remove qualquer candidato  
- Exporta a escala final  
- Troca senha de qualquer usuário  
- Visualiza tudo  

### **Médico**
- Só vê os plantões  
- Só pode se inscrever por si mesmo  
- Só pode remover a própria inscrição  
- Pode trocar a própria senha  
- Não vê dados de outros médicos  

---

## 📄 Estrutura da planilha (Google Sheets)

A planilha deve conter as abas:

### **1. plantoes**
```
data | horario | vagas | candidato1 | candidato2 | candidato3 | candidato4 | candidato5
```

### **2. medicos**
```
id | nome | email
```

### **3. usuarios**
```
email | senha_hash | nome | ativo | admin
```

### **4. logs**
```
timestamp | usuario | acao | plantao | detalhes
```

---

## 🚀 Deploy no Streamlit Cloud

1. Suba todos os arquivos `.py` para o GitHub  
2. No Streamlit Cloud, configure o repositório  
3. Em **Settings → Secrets**, cole o conteúdo do JSON da service account:

```
[gcp_service_account]
type="service_account"
project_id="..."
private_key_id="..."
private_key="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----"
client_email="..."
client_id="..."
token_uri="https://oauth2.googleapis.com/token"
```

⚠️ **Nunca coloque o arquivo JSON no GitHub.**

---

## 📤 Exportar escala final

Apenas o administrador vê o botão:

```
📥 Baixar escala final (CSV)
```

O arquivo contém todos os plantões e candidatos cadastrados.

---

## 🛠️ Dependências

`requirements.txt`:

```
streamlit
gspread
google-auth
bcrypt
pandas
```

---

## 🧪 Logs

Toda ação é registrada automaticamente:

- login  
- inscrição  
- remoção de inscrição  
- edição de plantões  
- exportação da escala  
- troca de senha  

Isso garante rastreabilidade total.

---

## 📞 Suporte

Para adicionar novos médicos, redefinir senhas ou ajustar permissões, basta editar a aba `usuarios` no Google Sheets.
