# Security
An overlooked part of serving your own infrastructure is security. When using one of the "big three" cloud services, most of this is taken care of. Even newer services like RunPod offer highly secure containers to serve models.

Since we are hosting on-prem, we need to think about these things ourselves. If you're in a university ecosystem, many system administrators will not allow you to provide services to the internet, while also granting access to internal file systems and secure shell (`ssh`) using something like Kerberos keys.

In order to make our system as secure as possible, we try to adopt a "defense-in-depth" approach -- providing multiple layers of protection, to make the attack surface as small as possible. In this document, we detail how we go about doing this.

> [!NOTE]
> It is fine to detail the methodology behind such defensive measures, but for obvious reasons, certain environment variables will be kept hidden. These should usually be contained within a `.env` file. There is an example of such a file in the relevant stack folders.

First, it is helpful to consider which aspects of the server we should protect.

**Secure Shell (ssh)**
In order to 