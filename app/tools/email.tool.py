from typing import Dict, List, Any, Optional
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pydantic import BaseModel, EmailStr, Field

logger = logging.getLogger(__name__)

class EmailRequest(BaseModel):
    """Modelo para requisição de envio de email."""
    to: List[EmailStr]
    subject: str
    body: str
    cc: Optional[List[EmailStr]] = None
    bcc: Optional[List[EmailStr]] = None
    html: bool = False

class EmailResponse(BaseModel):
    """Modelo para resposta de envio de email."""
    success: bool
    message: str
    recipients: List[str]
    error: Optional[str] = None

class EmailTool:
    """
    Ferramenta para envio de emails.
    Pode ser usada por agentes para comunicação externa.
    """
    
    def __init__(
        self,
        smtp_server: str,
        smtp_port: int,
        username: str,
        password: str,
        sender_email: str
    ):
        """
        Inicializa a ferramenta de email.
        
        Args:
            smtp_server: Servidor SMTP
            smtp_port: Porta do servidor SMTP
            username: Nome de usuário para autenticação
            password: Senha para autenticação
            sender_email: Email do remetente
        """
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.sender_email = sender_email
        
        logger.info(f"Ferramenta de email inicializada para servidor {smtp_server}:{smtp_port}")
    
    async def send_email(self, request: EmailRequest) -> EmailResponse:
        """
        Envia um email.
        
        Args:
            request: Parâmetros para o email
            
        Returns:
            Resultado do envio
        """
        logger.info(f"Enviando email para {request.to} com assunto: {request.subject}")
        
        try:
            # Criar mensagem
            msg = MIMEMultipart('alternative')
            msg['Subject'] = request.subject
            msg['From'] = self.sender_email
            msg['To'] = ', '.join(request.to)
            
            if request.cc:
                msg['Cc'] = ', '.join(request.cc)
            
            if request.bcc:
                msg['Bcc'] = ', '.join(request.bcc)
            
            # Adicionar corpo do email
            body_type = 'html' if request.html else 'plain'
            msg.attach(MIMEText(request.body, body_type))
            
            # Conectar ao servidor SMTP
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.username, self.password)
            
            # Construir lista completa de destinatários
            all_recipients = request.to.copy()
            if request.cc:
                all_recipients.extend(request.cc)
            if request.bcc:
                all_recipients.extend(request.bcc)
            
            # Enviar email
            server.sendmail(self.sender_email, all_recipients, msg.as_string())
            server.quit()
            
            logger.info(f"Email enviado com sucesso para {len(all_recipients)} destinatários")
            
            return EmailResponse(
                success=True,
                message="Email enviado com sucesso",
                recipients=all_recipients
            )
            
        except Exception as e:
            logger.error(f"Erro ao enviar email: {str(e)}")
            
            return EmailResponse(
                success=False,
                message="Falha ao enviar email",
                recipients=request.to,
                error=str(e)
            )

# Factory para criar instância da ferramenta com configurações
def create_email_tool(config: Dict[str, Any]) -> EmailTool:
    """
    Cria uma instância da ferramenta de email com as configurações fornecidas.
    
    Args:
        config: Configurações da ferramenta
        
    Returns:
        Instância da ferramenta de email
    """
    return EmailTool(
        smtp_server=config.get("smtp_server"),
        smtp_port=config.get("smtp_port", 587),
        username=config.get("username"),
        password=config.get("password"),
        sender_email=config.get("sender_email")
    )