# Preparation artifact. Default Inspect is read-only. No keys/certificates are created.
[CmdletBinding()]
param(
    [ValidateSet('Inspect','Install','StartJob','SignDetached')][string]$Mode='Inspect',
    [switch]$Apply,
    [string]$PythonExe,
    [string]$Packet,
    [ValidatePattern('^[0-9a-f]{64}$')][string]$OwnerPin,
    [ValidatePattern('^[0-9a-f]{64}$')][string]$QualifierPin,
    [ValidatePattern('^[0-9a-f]{64}$')][string]$CertificateSha256,
    [string]$InputPath,
    [string]$OutputPath,
    [string[]]$JobArguments
)
$ErrorActionPreference='Stop'
$ServiceName='BDBAuditNF02P0'
$ServiceAccount='NT SERVICE\BDBAuditNF02P0'
$Common=[Environment]::GetFolderPath([Environment+SpecialFolder]::CommonApplicationData)
$AuthorityParent=Join-Path $Common 'BDB Audit'
$AuthorityRoot=Join-Path $AuthorityParent 'NF02-P0-Limited'
$CampaignParent=Join-Path $AuthorityParent 'P0-Campaigns'

function Require-Admin {
    $principal=New-Object Security.Principal.WindowsPrincipal ([Security.Principal.WindowsIdentity]::GetCurrent())
    if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){throw 'Independent OS installer elevation required'}
}
function Assert-NoReparse([string]$Path) {
    $current=[IO.Path]::GetFullPath($Path)
    while($current){
        if(Test-Path -LiteralPath $current){
            if((Get-Item -LiteralPath $current -Force).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Reparse path denied'}
        }
        $parent=[IO.Directory]::GetParent($current)
        if($null -eq $parent){break};$current=$parent.FullName
    }
}
function Set-ResourceAcl([string]$Path,[string]$ServiceSid,[bool]$Writable=$false) {
    Assert-NoReparse $Path
    $item=Get-Item -LiteralPath $Path -Force
    if($item.PSIsContainer){$acl=New-Object Security.AccessControl.DirectorySecurity}else{$acl=New-Object Security.AccessControl.FileSecurity}
    $acl.SetAccessRuleProtection($true,$false)
    $acl.SetOwner((New-Object Security.Principal.SecurityIdentifier 'S-1-5-32-544'))
    foreach($id in @('S-1-5-18','S-1-5-32-544',$ServiceSid)){
        if(-not $id){continue}
        $rights=if($id -eq $ServiceSid){if($Writable){'Modify'}else{'ReadAndExecute'}}else{'FullControl'}
        $inherit=if($item.PSIsContainer){'ContainerInherit, ObjectInherit'}else{'None'}
        $rule=New-Object Security.AccessControl.FileSystemAccessRule ((New-Object Security.Principal.SecurityIdentifier $id),$rights,$inherit,'None','Allow')
        $acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}
function Write-NewBytes([string]$Path,[byte[]]$Bytes) {
    $stream=[IO.File]::Open([IO.Path]::GetFullPath($Path),[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
    try{$stream.Write($Bytes,0,$Bytes.Length);$stream.Flush($true)}finally{$stream.Dispose()}
}
if($Mode -eq 'Inspect'){
    $service=Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    [ordered]@{status='READ_ONLY_NOT_INSTALLATION_OR_RQ';os=[Environment]::OSVersion.VersionString;service=$ServiceName;
        installed=($null -ne $service);authority_root=$AuthorityRoot;root_present=(Test-Path -LiteralPath $AuthorityRoot);
        required_account=$ServiceAccount;current_identity=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value} | ConvertTo-Json -Compress
    exit 0
}
if(-not $Apply){throw 'Mutation requires explicit -Apply on an authorized qualification host; default Inspect is read-only'}
if($Mode -eq 'SignDetached'){
    if(-not $CertificateSha256 -or -not $InputPath -or -not $OutputPath){throw 'Exact public DER pin/input/new output required'}
    Assert-NoReparse $InputPath;Assert-NoReparse $OutputPath
    if((Get-Item -LiteralPath $InputPath).Length -gt 2MB){throw 'Signed input quota'}
    Add-Type -AssemblyName System.Security
    $matches=@(Get-ChildItem Cert:\CurrentUser\My | Where-Object {
        $sha=[Security.Cryptography.SHA256]::Create()
        try{([BitConverter]::ToString($sha.ComputeHash($_.RawData))).Replace('-','').ToLowerInvariant() -ceq $CertificateSha256}finally{$sha.Dispose()}
    })
    if($matches.Count -ne 1 -or -not $matches[0].HasPrivateKey){throw 'Real controlled signing certificate not uniquely available'}
    $cert=$matches[0];$chain=New-Object Security.Cryptography.X509Certificates.X509Chain
    try{
        $chain.ChainPolicy.RevocationMode=[Security.Cryptography.X509Certificates.X509RevocationMode]::Online
        $chain.ChainPolicy.RevocationFlag=[Security.Cryptography.X509Certificates.X509RevocationFlag]::ExcludeRoot
        $chain.ChainPolicy.UrlRetrievalTimeout=[TimeSpan]::FromSeconds(10)
        if(-not $chain.Build($cert) -or $chain.ChainElements.Count -lt 2){throw 'Current PKI/revocation unavailable or invalid'}
    }finally{$chain.Dispose()}
    $content=New-Object Security.Cryptography.Pkcs.ContentInfo (,[IO.File]::ReadAllBytes([IO.Path]::GetFullPath($InputPath)))
    $cms=New-Object Security.Cryptography.Pkcs.SignedCms ($content,$true)
    $signer=New-Object Security.Cryptography.Pkcs.CmsSigner $cert
    $signer.DigestAlgorithm=New-Object Security.Cryptography.Oid '2.16.840.1.101.3.4.2.1'
    $cms.ComputeSignature($signer,$false)
    Write-NewBytes $OutputPath ($cms.Encode())
    [ordered]@{status='DETACHED_CMS_WRITTEN';signer_der_sha256=$CertificateSha256} | ConvertTo-Json -Compress
    exit 0
}
Require-Admin
if($Mode -eq 'StartJob'){
    if(-not $JobArguments -or $JobArguments.Count -gt 24 -or $JobArguments[0] -notin @('status','prepare','accept','prepare-release','release')){throw 'Finite service job required'}
    if(@($JobArguments | Where-Object {$_.Length -gt 4096}).Count){throw 'Service argument quota'}
    $service=New-Object ServiceProcess.ServiceController $ServiceName
    try{
        $service.Refresh();if($service.Status -ne 'Stopped'){throw 'Serialized service is already running; no overlapping job'}
        $service.Start([string[]]$JobArguments)
    }finally{$service.Dispose()}
    [ordered]@{status='SCM_JOB_DISPATCHED_CHECK_EVENT_1001';service=$ServiceName} | ConvertTo-Json -Compress
    exit 0
}
if(-not $PythonExe -or -not $Packet -or -not $OwnerPin -or -not $QualifierPin){throw 'Final interpreter, signed packet and independent out-of-band pins required'}
Assert-NoReparse $PythonExe;Assert-NoReparse $Packet;Assert-NoReparse $AuthorityRoot;Assert-NoReparse $CampaignParent
if((Test-Path -LiteralPath $AuthorityRoot) -or (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue)){throw 'Refuse overwrite/reinstallation; existing installation needs separate approved maintenance'}
$verification=& $PythonExe -I -B (Join-Path $PSScriptRoot 'nf02_p0_verify_installation.py') --packet $Packet --owner-pin $OwnerPin --qualifier-pin $QualifierPin
if($LASTEXITCODE -ne 0){throw 'Signed packet/code/environment verification failed; no installation performed'}
$checked=$verification | ConvertFrom-Json
if($checked.status -cne 'SIGNED_PACKET_READBACK_PASS_OS_INSTALLATION_NOT_YET_QUALIFIED'){throw 'Unknown packet verifier result'}
$install=Get-Content -LiteralPath (Join-Path $Packet 'installation.json') -Raw | ConvertFrom-Json
$namespace=$checked.namespace_authority_digest
$serviceSid=$checked.service_sid
$CampaignRoot=Join-Path $CampaignParent $namespace
# Parent must be independently protected. Do not change any pre-existing legacy parent ACL.
if(Test-Path -LiteralPath $AuthorityParent){
    & $PythonExe -I -B -c 'from bdb_audit.history.installation_authority import _protected; import sys; _protected(sys.argv[1])' $AuthorityParent
    if($LASTEXITCODE -ne 0){throw 'Existing BDB Audit parent is not protected; independent installer must resolve it separately'}
}else{[void](New-Item -ItemType Directory -Path $AuthorityParent);Set-ResourceAcl $AuthorityParent $serviceSid}
if(Test-Path -LiteralPath $CampaignRoot){throw 'Qualification campaign namespace must be new'}
[void](New-Item -ItemType Directory -Path $AuthorityRoot)
Set-ResourceAcl $AuthorityRoot $serviceSid
# Copy only verified installed membership plus exact root/installation and signature.
foreach($name in @('root.json','installation.json','installation.p7s')+@($install.installed_files | ForEach-Object {$_.file})){
    $source=Join-Path $Packet $name;$target=Join-Path $AuthorityRoot $name
    Assert-NoReparse $source
    $parent=Split-Path -Parent $target
    if(-not (Test-Path -LiteralPath $parent)){[void](New-Item -ItemType Directory -Path $parent -Force)}
    Copy-Item -LiteralPath $source -Destination $target -ErrorAction Stop
}
[void](New-Item -ItemType Directory -Path (Join-Path $AuthorityRoot 'grants'))
foreach($item in @(Get-ChildItem -LiteralPath $AuthorityRoot -Recurse -Force)) {Set-ResourceAcl $item.FullName $serviceSid}
if(-not (Test-Path -LiteralPath $CampaignParent)){[void](New-Item -ItemType Directory -Path $CampaignParent);Set-ResourceAcl $CampaignParent $serviceSid}
else{
    & $PythonExe -I -B -c 'from bdb_audit.history.installation_authority import _protected; import sys; _protected(sys.argv[1])' $CampaignParent
    if($LASTEXITCODE -ne 0){throw 'Existing campaign parent is not protected'}
}
[void](New-Item -ItemType Directory -Path $CampaignRoot)
Set-ResourceAcl $CampaignRoot $serviceSid $true
# Runtime/stdlib/Git/code trees must already be protected by provisioning. This
# script does not recursively take ownership of a caller-selected interpreter.
$binary='"'+[IO.Path]::GetFullPath($PythonExe)+'" -I -B -m bdb_audit.p0_service'
& sc.exe create $ServiceName binPath= $binary start= demand obj= $ServiceAccount DisplayName= 'BDB Audit NF02 P0'
if($LASTEXITCODE -ne 0){throw 'SCM creation failed; partial installation is retained for installer inspection'}
& sc.exe sidtype $ServiceName unrestricted
if($LASTEXITCODE -ne 0){throw 'SCM service SID configuration failed'}
$resolved=(New-Object Security.Principal.NTAccount $ServiceAccount).Translate([Security.Principal.SecurityIdentifier]).Value
if($resolved -cne $serviceSid){throw 'Actual service SID differs from signed installation'}
# Demand-start one-command host. Automatic SCM restart cannot recover transient
# StartService arguments. Reissue exact signed job explicitly after readback.
[ordered]@{status='INSTALLED_NOT_RQ_PASS';service=$ServiceName;authority_root=$AuthorityRoot;
    campaign_root=$CampaignRoot;installation_sha256=$checked.installation_sha256;next='Install signed grants; run real service/ACL/RQ checks'} | ConvertTo-Json -Compress
