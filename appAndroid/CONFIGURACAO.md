# 📱 Configuração do App Android

## ✅ Pré-requisitos
- Android Studio instalado
- Java JDK 8 ou superior
- SDK Android API 34

## 🚀 Passos para Compilar

### 1. Configurar URL do Servidor
Edite `app/src/main/java/com/auditoria/app/MainActivity.java`:
```java
private static final String SERVER_URL = "http://SEU_IP:8501";
```

### 2. Configurar Streamlit para Acesso Externo
No servidor onde roda o Streamlit:
```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

### 3. Abrir no Android Studio
1. Abra o Android Studio
2. `File` → `Open` → Selecione a pasta `appAndroid`
3. Aguarde o Gradle sync

### 4. Compilar e Instalar
1. Conecte seu celular Android via USB
2. Ative `Developer Options` e `USB Debugging` no celular
3. Clique em `Run` (▶️) no Android Studio
4. Selecione seu dispositivo

## 🌐 Acesso via Wi-Fi

### Opção A: Rede Local
- Celular e servidor na mesma rede Wi-Fi
- Use o IP local do servidor (ex: 192.168.1.9)

### Opção B: Acesso Remoto
1. Configure port forwarding no roteador (porta 8501)
2. Use seu IP público ou domínio
3. Recomenda-se usar HTTPS com certificado

## 🔧 Troubleshooting

### Erro de Conexão
- Verifique se o Streamlit está rodando
- Confirme o IP e porta no MainActivity.java
- Teste no navegador do celular primeiro

### Erro de Permissão
- O app pede permissões automaticamente
- Aceite todas as permissões solicitadas

### App Fecha Sozinho
- Verifique os logs no Android Studio (Logcat)
- Confirme se a URL está correta

## 📦 Gerar APK para Distribuição

1. No Android Studio: `Build` → `Generate Signed Bundle / APK`
2. Selecione `APK`
3. Crie ou use uma keystore
4. Selecione `release` build variant
5. O APK será gerado em `app/release/`

##  Personalização

### Ícone do App
Substitua os arquivos em `app/src/main/res/mipmap-*/`

### Cores
Edite `app/src/main/res/values/themes.xml`

### Nome do App
Edite `app/src/main/res/values/strings.xml`
