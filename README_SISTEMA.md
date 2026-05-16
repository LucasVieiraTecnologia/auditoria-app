# 🏢 Auditoria Inteligente - Sistema Completo

## ✅ Funcionalidades Implementadas

### 🔐 Sistema de Autenticação
- **Login seguro** com hash de senha
- **Múltiplos usuários** configuráveis via `.env`
- **Sessão protegida** até logout
- **Logs de acesso** completos

### 📊 Logs de Acesso (Admin)
- Registro de todos os logins (sucesso/falha)
- Registro de logouts
- Data/hora e IP de cada acesso
- Visualização na sidebar (apenas admin)
- Opção de limpar logs

### 👥 Gerenciamento de Usuários
No arquivo `.env`:
```env
# Usuário principal (admin)
APP_USERNAME=admin
APP_PASSWORD=Admin@2026!

# Usuários adicionais
APP_USERS=joao:senha123,maria:senha456
```

### 📱 App Android
- **WebView nativo** com todas as funcionalidades
- **Pull-to-refresh** para atualizar
- **Download de arquivos** integrado
- **Upload de PDFs** funcional
- **Permissões** configuradas
- **Design responsivo**

## 🚀 Como Usar

### 1. Acesso Web
1. Acesse `http://localhost:8501`
2. Login: `admin` / `Admin@2026!`
3. Use normalmente

### 2. Adicionar Usuários
Edite `.env`:
```env
APP_USERS=usuario1:senha1,usuario2:senha2
```

### 3. Ver Logs de Acesso
1. Faça login como admin
2. Na sidebar, expanda "📊 Logs de Acesso"
3. Veja todos os registros

### 4. App Android
1. Execute `configurar_ip.bat` na pasta `appAndroid`
2. Abra o projeto no Android Studio
3. Compile e instale no celular

## 📁 Estrutura de Arquivos

```
D:\Auditoria\
├── app.py                      # Aplicação principal
├── rodar_auditoria_script.py   # Motor de extração
├── logs_acesso.py              # Sistema de logs
├── .env                        # Configurações
├── appAndroid/                 # App Android
│   ├── app/
│   │   └── src/main/
│   │       ├── java/.../MainActivity.java
│   │       ├── res/
│   │       └── AndroidManifest.xml
│   ├── build.gradle
│   ├── settings.gradle
│   ├── configurar_ip.bat
│   ├── CONFIGURACAO.md
│   └── README.md
└── ...
```

## 🔒 Segurança

- Senhas com hash SHA-256
- Logs de todas as tentativas de acesso
- Sessão protegida
- HTTPS recomendado para produção

## 📋 Próximos Passos (Opcional)

- [ ] Banco de dados para usuários
- [ ] Recuperação de senha
- [ ] App iOS
- [ ] Notificações push
- [ ] Modo offline
