# Auditoria Inteligente - App Android

## 📱 Sobre
App Android para acessar o sistema de Auditoria Inteligente de Condomínios.

## 🚀 Como Usar

### Opção 1: WebView App (Recomendado)
1. Instale o Android Studio
2. Abra a pasta `appAndroid` como projeto
3. Conecte seu celular ou use emulador
4. Execute o app

### Opção 2: PWA (Progressive Web App)
1. Acesse o site no Chrome do Android
2. Toque em "Adicionar à tela inicial"
3. O app funcionará como nativo

## ⚙️ Configuração

### URL do Servidor
Edite o arquivo `app/src/main/java/com/auditoria/app/MainActivity.java`:
```java
private static final String SERVER_URL = "http://SEU_IP:8501";
```

### Para acesso externo:
1. No Streamlit, use: `streamlit run app.py --server.address 0.0.0.0`
2. Configure o roteador para liberar a porta 8501
3. Use seu IP público ou dominio no app

## 📋 Permissões
- Internet: Necessário para acessar o servidor
- Armazenamento: Para download de relatórios

## 🔐 Segurança
- Use HTTPS em produção
- Configure firewall adequadamente
- Mantenha credenciais seguras
