const SERVICE_DESCRIPTIONS: Record<string, string> = {
  DNS: "Domain Name System translates names such as example.com into IP addresses. An exposed DNS service commonly listens on TCP/UDP port 53.",
  HTTP: "Hypertext Transfer Protocol serves unencrypted web pages or local administration interfaces, commonly on TCP port 80.",
  HTTPS:
    "Encrypted web traffic or secure administration interfaces using TLS, commonly on TCP port 443. NetWatch cannot read encrypted page contents.",
  SSH: "Secure Shell provides encrypted remote command-line administration and file transfer, commonly on TCP port 22.",
  SMB: "Server Message Block is used for Windows file, printer, and network-share access, commonly on TCP port 445.",
  RDP: "Remote Desktop Protocol provides graphical remote access to Windows computers, commonly on TCP port 3389.",
};

export function describeService(name: string, port: number) {
  return (
    SERVICE_DESCRIPTIONS[name.toUpperCase()] ??
    `${name} was identified by a safe TCP connection check on approved port ${port}. An open port means a service accepted a connection; it is not automatically a vulnerability.`
  );
}
