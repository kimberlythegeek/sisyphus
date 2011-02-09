import re
try:
    import json
except:
    import simplejson as json


# http://code.google.com/p/socorro/wiki/SignatureGeneration
# http://code.google.com/p/socorro/source/browse/trunk/socorro/processor/processor.py#356
# http://code.google.com/p/socorro/source/browse/trunk/socorro/processor/processor.py#332

# generateSignatureFromList customizations

# a list of frame signatures that should always be considered top of the stack if present in the stack
signatureSentinels = [
    '_purecall',
    'JS_Assert',
    ('mozilla::ipc::RPCChannel::Call(IPC::Message*, IPC::Message*)',
     lambda x: 'CrashReporter::CreatePairedMinidumps(void*, unsigned long,nsAString_internal*, nsILocalFile**, nsILocalFile**)' in x)
    ]

# a regular expression matching frame signatures that should be ignored when generating an overall signature
reIrrelevantSignature = re.compile(r'@0x[0-9a-fA-F]{2,}|@0x[1-9a-fA-F]|RaiseException|_CxxThrowException|Abort|___TERMINATING_DUE_TO_UNCAUGHT_EXCEPTION___|_NSRaiseError|mozilla::ipc::RPCChannel::Call\(IPC::Message\*, IPC::Message\*\)|mozalloc_abort|NS_DebugBreak_P|linux-gate\.so')

# a regular expression matching frame signatures that should always be coupled with the following frame signature when generating an overall signature
rePrefixSignature = re.compile(r'@0x0|strchr|strstr|strlen|PL_strlen|strcmp|wcslen|memcpy|memmove|memcmp|malloc|realloc|.*free|arena_dalloc_small|arena_alloc|arena_dalloc|nsObjCExceptionLogAbort(\(.*?\)){0,1}|libobjc.A.dylib@0x1568.|nsCOMPtr_base::assign_from_qi\(nsQueryInterface, nsIDconst&\)|objc_msgSend|_purecall|nsTArray_base::ShiftData\(unsigned int, unsigned int, unsigned int, unsigned int\)|PL_DHashTableOperate|EtwEventEnabled|RtlpFreeHandleForAtom|RtlpDeCommitFreeBlock|RtlpAllocateAffinityIndex|RtlAddAccessAllowedAce|RtlQueryPerformanceFrequency|RtlpWaitOnCriticalSection|RtlpWaitForCriticalSection|_PR_MD_ATOMIC_(INC|DEC)REMENT|nsCOMPtr.*|nsRefPtr.*|operator new\([^,)]+\)|CFRelease|objc_exception_throw|[-+]\[NSException raise(:format:(arguments:)?)?\]|JS_Assert')

# parse_crashreport customizations

# any signatures that match this list should be combined with their associated source code line numbers
reSignaturesWithLineNumbers = re.compile(r'js_Interpret')


def generateSignatureFromList(signatureList):
    """
    each element of signatureList names a frame in the crash stack; and is:
    - a prefix of a relevant frame: Append this element to the signature
    - a relevant frame: Append this element and stop looking
    - irrelevant: Append this element only after we have seen a prefix frame
    The signature is a ' | ' separated string of frame names
    Although the database holds only 255 characters, we don't truncate here
    """

    # shorten signatureList to the first signatureSentinel
    sentinelLocations = []
    for aSentinel in signatureSentinels:
        if type(aSentinel) == tuple:
            aSentinel, conditionFn = aSentinel
            if not conditionFn(signatureList):
                continue
        try:
            sentinelLocations.append(signatureList.index(aSentinel))
        except ValueError:
            pass
    if sentinelLocations:
        signatureList = signatureList[min(sentinelLocations):]

    newSignatureList = []
    prefixFound = False
    ignored_frame_count = 0

    for aSignature in signatureList:
        if reIrrelevantSignature.match(aSignature):
            if prefixFound:
                newSignatureList.append(aSignature)
            else:
                ignored_frame_count += 1
            continue
        newSignatureList.append(aSignature)
        if not rePrefixSignature.match(aSignature):
            break
        prefixFound = True

    socorroSignature = ' | '.join(newSignatureList)
    if socorroSignature == "":
        socorroSignature = '(no signature)'

    sisyphusSignatureList = [socorroSignature]
    sisyphusSignatureList.extend(signatureList[len(newSignatureList) + ignored_frame_count:])
    sisyphusSignatureList = sisyphusSignatureList[:5]

    return sisyphusSignatureList

def parse_crashreport(crashreport):

    reBlankLine           = re.compile(r'\s*$')
    reInitOperatingSystem = re.compile(r'Operating system: (.*)')
    reCpuType             = re.compile(r'CPU:\s(.*)')
    reCpuCount            = re.compile(r'\s+([0-9]+)\sCPU')
    reCrashReason         = re.compile(r'Crash reason:\s+(.*)')
    reCrashAddress        = re.compile(r'Crash address:\s+(.*)')
    reCrashThread         = re.compile(r'Thread ([0-9]+) [(]crashed[)]')
    reFrameModule         = re.compile(r'\s*([0-9]+)\s+([^!]+)!(.*) [\[](.*) : ([0-9]+) \+ 0x[0-9a-fA-F]+[\]]')
    reFrameLibrary        = re.compile(r'\s*([0-9]+)\s+([^+]+)\s\+\s(0x[0-9a-fA-F]+)')
    reFrameAddress        = re.compile(r'\s*([0-9]+)\s+(0x[0-9a-fA-F]+)')
    reFrameRegister       = re.compile(r'\s+([a-zA-Z0-9]+)\s=\s(0x[0-9a-fA-F]+)')
    reFrameFoundBy        = re.compile(r'\s+Found by:')

    # socorro processor
    reFixupSpace = re.compile(r' (?=[\*&,])')
    reFixupComma = re.compile(r',(?! )')
    reFixupInteger = re.compile(r'(<|, )(\d+)([uUlL]?)([^\w])')

    crash_data = {
        "operating_system" : "",
        "operating_system_version" : "",
        "cpu_type" : "",
        "cpu_family" : "",
        "cpu_count" : "",
        "crash_address" : "",
        "crashing_thread" : "",
        "frames" : [],
        "messages": []
        }

    frames = crash_data['frames']
    messages = crash_data['messages']

    state = 'init'

    lines = crashreport.split('\n')

    while len(lines) > 0:

        line = lines.pop(0)

        messages.append("state: %s, line: '%s'" % (state, line))

        if state == 'init':
            if not line:
                continue

            match = reInitOperatingSystem.match(line)
            if match:
                crash_data['operating_system'] = match.group(1)
                state = 'expect_operating_system_version'
            else:
                messages.append('error state: %s, unexpected: %s' % (state, line))
            continue

        if state == 'expect_operating_system_version':
            crash_data['operating_system_version'] = line.strip()
            state = 'expect_cpu_type'
            continue

        if state == 'expect_cpu_type':
            match = reCpuType.match(line)
            if match:
                crash_data['cpu_type'] = match.group(1)
                state = 'expect_cpu_family_or_count'
            else:
                messages.append('error state: %s, unexpected: %s' % (state, line))
            continue

        if state == 'expect_cpu_family_or_count':
            lines.insert(0, line)
            match = reCpuCount.match(line)
            if match:
                state = 'expect_cpu_count'
            else:
                state = 'expect_cpu_family'
            continue

        if state == 'expect_cpu_family':
            crash_data['cpu_family'] = line.strip()
            state = 'expect_cpu_count'
            continue

        if state == 'expect_cpu_count':
            match = reCpuCount.match(line)
            if match:
                crash_data['cpu_count'] = match.group(1)
                state = 'expect_crash_reason_blank_line'
            else:
                messages.append('error state: %s, unexpected: %s' % (state, line))
            continue

        if state == 'expect_crash_reason_blank_line':
            match = reBlankLine.match(line)
            if match:
                state = 'expect_crash_reason'
            else:
                messages.append('error state: %s, unexpected: %s' % (state, line))
            continue

        if state == 'expect_crash_reason':
            match = reCrashReason.match(line)
            if match:
                crash_data['crash_reason'] = match.group(1)
                state = 'expect_crash_address'
            else:
                messages.append('error state: %s, unexpected: %s' % (state, line))
            continue

        if state == 'expect_crash_address':
            match = reCrashAddress.match(line)
            if match:
                crash_data['crash_address'] = match.group(1)
                state = 'expect_thread_crash_blank_line'
            else:
                messages.append('error state: %s, unexpected: %s' % (state, line))
            continue

        if state == 'expect_thread_crash_blank_line':
            match = reBlankLine.match(line)
            if match:
                state = 'expect_thread_crash'
                continue
            else:
                messages.append('error state: %s, unexpected: %s' % (state, line))
            continue

        if state == 'expect_thread_crash':
            match = reCrashThread.match(line)
            if match:
                crash_data['crashing_thread'] = match.group(1)
                state = 'expect_frame_start'
            else:
                messages.append('error state: %s, unexpected: %s' % (state, line))
            continue

        if state == 'expect_frame_start':
            messages.append('checking reFrameModule')
            match = reFrameModule.match(line)
            if match:
                messages.append('found')
                frame =  {
                    'frame_type' : 'module',
                    'frame_number' : match.group(1),
                    'frame_module' : match.group(2),
                    'frame_function' : match.group(3),
                    'frame_filename' : match.group(4),
                    'frame_linenumber' : match.group(5),
                    'frame_registers' : {}
                    }

                if reSignaturesWithLineNumbers.match(frame['frame_function']):
                    frame['frame_signature'] = "%s:%s" % (frame['frame_function'], frame['frame_linenumber'])
                else:
                    frame['frame_signature'] = frame['frame_function']

                # Remove spaces before all stars, ampersands, and commas
                frame['frame_signature'] = reFixupSpace.sub('', frame['frame_signature'])

                # Ensure a space after commas
                frame['frame_signature'] = reFixupComma.sub(', ', frame['frame_signature'])

                # normalize template signatures with manifest const integers to 'int': Bug 481445
                frame['frame_signature'] = reFixupInteger.sub(r'\1int\4', frame['frame_signature'])

                frames.append(frame)
                state = 'expect_frame_registers'
            else:
                messages.append('checking reFrameLibrary')
                match = reFrameLibrary.match(line)
                if match:
                    messages.append('found')
                    frame = {
                        'frame_type' : 'library',
                        'frame_number' : match.group(1),
                        'frame_library' : match.group(2),
                        'frame_library_address' : match.group(3),
                        'frame_registers' : {}
                        }
                    frame['frame_signature'] = '%s@%s' % (frame['frame_library'], frame['frame_library_address'])
                    frames.append(frame)
                    state = 'expect_frame_registers'
                else:
                    messages.append('checking reFrameAddress')
                    match = reFrameAddress.match(line)
                    if match:
                        messages.append('found')
                        frame = {
                            'frame_type' : 'address',
                            'frame_number' : match.group(1),
                            'frame_address' : match.group(2),
                            'frame_registers' : {}
                            }
                        frame['frame_signature'] = '@%s' % frame['frame_address']
                        frames.append(frame)
                        state = 'expect_frame_registers'
                    else:
                        messages.append('checking reBlankLine')
                        match = reBlankLine.match(line)
                        if match:
                            messages.append('found')
                            state = 'complete'
                            break
            continue

        if state == 'expect_frame_registers':
            match = re.search(reFrameRegister, line)
            if match:
                while match:
                    frames[-1]['frame_registers'][match.group(1)] = match.group(2)
                    match = reFrameRegister.search(line, match.end(0))
            else:
                match = reFrameFoundBy.match(line)
                if match:
                    state = 'expect_frame_start'
                else:
                    messages.append('error state: %s, unexpected: %s' % (state, line))
            continue

        messages.append('error state: %s, unexpected: %s' % (state, line))
        continue

    messages.append("state: %s" % state)

    signatureList = [frame['frame_signature'] for frame in crash_data['frames']]

    crash_data['signature_list'] = generateSignatureFromList(signatureList)

    return crash_data

if __name__ == "__main__":

    crashreport_list = ["""
Operating system: Linux
                  0.0.0 Linux 2.6.18-194.17.4.el5 #1 SMP Mon Oct 25 15:51:07 EDT 2010 i686
CPU: x86
     GenuineIntel family 6 model 23 stepping 6
     1 CPU

Crash reason:  SIGSEGV
Crash address: 0x6ea35800

Thread 0 (crashed)
 0  0x6ea35800
    eip = 0x6ea35800   esp = 0xbfbaca00   ebp = 0x3800c878   ebx = 0x021e20f0
    esi = 0x65646e69   edi = 0x01b34210   eax = 0x00000000   ecx = 0x00000010
    edx = 0x0004b7b8   efl = 0x00010282
    Found by: given as instruction pointer in context
 1  libgobject-2.0.so.0.1200.3 + 0x37f77
    eip = 0x00335f78   esp = 0xbfbaca2c   ebp = 0x3800c878
    Found by: stack scanning
 2  libatk-1.0.so.0.1212.0 + 0x7ff
    eip = 0x0015c800   esp = 0xbfbaca4c   ebp = 0x3800c878
    Found by: stack scanning
 3  libxul.so!nsEditor::InstallEventListeners() [nsEditor.cpp : 375 + 0x67]
    eip = 0x011d4800   esp = 0xbfbaca60   ebp = 0x3800c878
    Found by: stack scanning
 4  libnspr4.so!_PR_InitIO [ptio.c : 1146 + 0x9]
    eip = 0x00146800   esp = 0xbfbaca8c   ebp = 0x3800c878
    Found by: stack scanning
 5  libxul.so!nsDetectionAdaptor::Init(nsIWebShellServices*, nsICharsetDetector*, nsIDocument*, nsIParser*, char const*, char const*) [nsDetectionAdaptor.cpp : 139 + 0x1e]
    eip = 0x00a57000   esp = 0xbfbacaa4   ebp = 0x3800c878
    Found by: stack scanning
 6  libxul.so!nsDetectionAdaptor::Init(nsIWebShellServices*, nsICharsetDetector*, nsIDocument*, nsIParser*, char const*, char const*) [nsDetectionAdaptor.cpp : 140 + 0xa]
    eip = 0x00a57013   esp = 0xbfbacab8   ebp = 0x3800c878
    Found by: stack scanning
 7  libxul.so!nsZipArchive::nsZipArchive() [nsZipArchive.cpp : 799 + 0x3]
    eip = 0x00a5c000   esp = 0xbfbacad0   ebp = 0x3800c878
    Found by: stack scanning
 8  libnspr4.so!PR_GetThreadPrivate [prtpd.c : 232 + 0x4]
    eip = 0x0012fa8b   esp = 0xbfbacb00   ebp = 0x3800c878
    Found by: stack scanning
 9  libc-2.5.so + 0x68ee5
    eip = 0x0445bee6   esp = 0xbfbacb0c   ebp = 0x3800c878
    Found by: stack scanning
10  libpthread-2.5.so + 0xa9c4
    eip = 0x0035d9c5   esp = 0xbfbacb30   ebp = 0x3800c878
    Found by: stack scanning
11  libnspr4.so!PR_GetCurrentThread [ptthread.c : 655 + 0xd]
    eip = 0x0014c266   esp = 0xbfbacb40   ebp = 0x3800c878
    Found by: stack scanning
12  libc-2.5.so + 0x126de1
    eip = 0x04519de2   esp = 0xbfbacb48   ebp = 0x3800c878
    Found by: stack scanning
13  libxul.so!nsObserverService::EnumerateObservers(char const*, nsISimpleEnumerator**) [nsObserverService.cpp : 168 + 0x6]
    eip = 0x01afcff2   esp = 0xbfbacb58   ebp = 0x3800c878
    Found by: stack scanning
14  libxul.so!SearchTable [pldhash.c : 415 + 0xc]
    eip = 0x01ad6d4f   esp = 0xbfbacb60   ebp = 0x3800c878
    Found by: stack scanning
15  libnspr4.so!PR_GetThreadPrivate [prtpd.c : 232 + 0x4]
    eip = 0x0012fa8b   esp = 0xbfbacb70   ebp = 0x3800c878
    Found by: stack scanning
16  libc-2.5.so + 0x68ee5
    eip = 0x0445bee6   esp = 0xbfbacb7c   ebp = 0x3800c878
    Found by: stack scanning
17  libxul.so!nsCharPtrHashKey::HashKey(char const*) [nsHashKeys.h : 334 + 0xa]
    eip = 0x0158bda6   esp = 0xbfbacb80   ebp = 0x3800c878
    Found by: stack scanning
18  libpthread-2.5.so + 0xa9c4
    eip = 0x0035d9c5   esp = 0xbfbacb90   ebp = 0x3800c878
    Found by: stack scanning
19  libnspr4.so!PR_GetCurrentThread [ptthread.c : 655 + 0xd]
    eip = 0x0014c266   esp = 0xbfbacba0   ebp = 0x3800c878
    Found by: stack scanning
20  libnspr4.so!PR_GetCurrentThread [ptthread.c : 655 + 0xd]
    eip = 0x0014c266   esp = 0xbfbacbb0   ebp = 0x3800c878
    Found by: stack scanning
21  libc-2.5.so + 0x126de1
    eip = 0x04519de2   esp = 0xbfbacbb8   ebp = 0x3800c878
    Found by: stack scanning
22  libnspr4.so!PR_GetThreadPrivate [prtpd.c : 232 + 0x4]
    eip = 0x0012fa8b   esp = 0xbfbacbd0   ebp = 0x3800c878
    Found by: stack scanning
23  libxul.so!NS_LogRelease_P [nsTraceRefcntImpl.cpp : 1036 + 0x18]
    eip = 0x01b5e23c   esp = 0xbfbacbf0   ebp = 0x3800c878
    Found by: stack scanning
24  libc-2.5.so + 0x699e8
    eip = 0x0445c9e9   esp = 0xbfbacc08   ebp = 0x3800c878
    Found by: stack scanning
25  libpthread-2.5.so + 0xa9c4
    eip = 0x0035d9c5   esp = 0xbfbacc10   ebp = 0x3800c878
    Found by: stack scanning
26  libxul.so!nsObserverService::Release() [nsObserverService.cpp : 76 + 0x75]
    eip = 0x01afc8a4   esp = 0xbfbacc40   ebp = 0x3800c878
    Found by: stack scanning
27  libxul.so!ProfileChangeStatusImpl::Release() [nsXREDirProvider.cpp : 833 + 0x116]
    eip = 0x008187b4   esp = 0xbfbacc50   ebp = 0x3800c878
    Found by: stack scanning
28  libxul.so!nsObserverService::NotifyObservers(nsISupports*, char const*, unsigned short const*) [nsObserverService.cpp : 185 + 0x17]
    eip = 0x01afd153   esp = 0xbfbacc60   ebp = 0x3800c878
    Found by: stack scanning
29  libfreetype.so.6.3.10 + 0x4d7d9
    eip = 0x080007da   esp = 0xbfbacc88   ebp = 0x3800c878
    Found by: stack scanning
30  libxul.so!deflate_stored [deflate.c : 1438 + 0xc]
    eip = 0x01d30136   esp = 0xbfbacc8c   ebp = 0x3800c878
    Found by: stack scanning
31  libxul.so!ScopedXPCOMStartup::~ScopedXPCOMStartup() [nsAppRunner.cpp : 1050 + 0x4]
    eip = 0x0080668d   esp = 0xbfbacd00   ebp = 0x3800c878
    Found by: stack scanning
32  libxul.so!nsCOMPtr<nsIPrefService>::~nsCOMPtr() [nsCOMPtr.h : 510 + 0x15]
    eip = 0x00811852   esp = 0xbfbacd10   ebp = 0x3800c878
    Found by: stack scanning
33  libxul.so!XRE_main [nsAppRunner.cpp : 3527 + 0x2c]
    eip = 0x0080eeff   esp = 0xbfbacd30   ebp = 0x3800c878
    Found by: stack scanning
34  libxul.so!nsLocalFile::GetDiskSpaceAvailable(long long*) [nsLocalFileUnix.cpp : 1185 + 0xa]
    eip = 0x01b3624c   esp = 0xbfbacd58   ebp = 0x3800c878
    Found by: stack scanning
35  libxul.so!nsLocalFile::Create(unsigned int, unsigned int) [nsLocalFileUnix.cpp : 488 + 0x6]
    eip = 0x01b34210   esp = 0xbfbacd5c   ebp = 0x3800c878
    Found by: stack scanning
36  libxul.so!nsSVGGraphicElement::AddRef() [nsSVGGraphicElement.cpp : 56 + 0x43]
    eip = 0x01404cd0   esp = 0xbfbacd60   ebp = 0x3800c878
    Found by: stack scanning
37  libxul.so!nsLocalFile::FillStatCache() [nsLocalFileUnix.cpp : 282 + 0x6]
    eip = 0x01b33b64   esp = 0xbfbacd64   ebp = 0x3800c878
    Found by: stack scanning
38  libxul.so!nsLocalFile::Create(unsigned int, unsigned int) [nsLocalFileUnix.cpp : 488 + 0x6]
    eip = 0x01b34210   esp = 0xbfbacd68   ebp = 0x3800c878
    Found by: stack scanning
39  libxul.so!nsDOMWorkerMessageHandler::SetOnXListener(nsAString_internal const&, nsIDOMEventListener*) [nsDOMWorkerMessageHandler.cpp : 166 + 0x16]
    eip = 0x011a0002   esp = 0xbfbacd6c   ebp = 0x3800c878
    Found by: stack scanning
40  libxul.so!nsToolkitProfileLock::Init(nsILocalFile*, nsILocalFile*, nsIProfileUnlocker**) [nsToolkitProfileService.cpp : 318 + 0x1]
    eip = 0x00821fd2   esp = 0xbfbacd7c   ebp = 0x3800c878
    Found by: stack scanning
41  libxul.so!nsToolkitProfileLock::GetDirectory(nsILocalFile**) [nsToolkitProfileService.cpp : 330 + 0x6]
    eip = 0x00822064   esp = 0xbfbacd80   ebp = 0x3800c878
    Found by: stack scanning
42  libxul.so!nsPrefService::GetBranch(char const*, nsIPrefBranch**) [nsPrefService.cpp : 232 + 0x7]
    eip = 0x00a744c0   esp = 0xbfbacd94   ebp = 0x3800c878
    Found by: stack scanning
43  libxul.so!nsPrefBranch::SetBoolPref(char const*, int) [nsPrefBranch.cpp : 178 + 0x1]
    eip = 0x00a6fd3a   esp = 0xbfbacd98   ebp = 0x3800c878
    Found by: stack scanning
44  libc-2.5.so + 0x68ee5
    eip = 0x0445bee6   esp = 0xbfbacd9c   ebp = 0x3800c878
    Found by: stack scanning
45  libxul.so!nsCommandLine::resolveShortcutURL(nsILocalFile*, nsACString_internal&) [nsCommandLine.cpp : 503 + 0x9]
    eip = 0x015d4eac   esp = 0xbfbacda4   ebp = 0x3800c878
    Found by: stack scanning
46  libxul.so!nsObserverService::EnumerateObservers(char const*, nsISimpleEnumerator**) [nsObserverService.cpp : 168 + 0x6]
    eip = 0x01afcff2   esp = 0xbfbacda8   ebp = 0x3800c878
    Found by: stack scanning
47  libxul.so!nsGTKRemoteService::QueryInterface(nsID const&, void**) [nsGTKRemoteService.cpp : 94 + 0x65]
    eip = 0x0192f7be   esp = 0xbfbacdac   ebp = 0x3800c878
    Found by: stack scanning
48  libxul.so!gfxTextRun::AllocateDetailedGlyphs(unsigned int, unsigned int) [gfxFont.cpp : 2755 + 0x4d]
    eip = 0x01bacdcc   esp = 0xbfbacdb0   ebp = 0x3800c878
    Found by: stack scanning
49  libstdc++.so.6.0.8 + 0x33cfe
    eip = 0x033f1cff   esp = 0xbfbacdbc   ebp = 0x3800c878
    Found by: stack scanning
50  libc-2.5.so + 0x126de1
    eip = 0x04519de2   esp = 0xbfbacdd8   ebp = 0x3800c878
    Found by: stack scanning
51  libc-2.5.so + 0x68ee5
    eip = 0x0445bee6   esp = 0xbfbacddc   ebp = 0x3800c878
    Found by: stack scanning
52  libc-2.5.so + 0x699e8
    eip = 0x0445c9e9   esp = 0xbfbacde8   ebp = 0x3800c878
    Found by: stack scanning
53  libc-2.5.so + 0xc793
    eip = 0x043ff794   esp = 0xbfbacdec   ebp = 0x3800c878
    Found by: stack scanning
54  libxul.so!nsAutoPtr<nsINIParser_internal::INIValue>::~nsAutoPtr() [nsAutoPtr.h : 102 + 0xc]
    eip = 0x01adceeb   esp = 0xbfbacdf0   ebp = 0x3800c878
    Found by: stack scanning
55  libstdc++.so.6.0.8 + 0x123
    eip = 0x033be124   esp = 0xbfbace00   ebp = 0x3800c878
    Found by: stack scanning
56  libpthread-2.5.so + 0x536
    eip = 0x00353537   esp = 0xbfbace44   ebp = 0x3800c878
    Found by: stack scanning
57  libc-2.5.so + 0x126de1
    eip = 0x04519de2   esp = 0xbfbace58   ebp = 0x3800c878
    Found by: stack scanning
58  libc-2.5.so + 0x68ee5
    eip = 0x0445bee6   esp = 0xbfbace5c   ebp = 0x3800c878
    Found by: stack scanning
59  libc-2.5.so + 0x69b60
    eip = 0x0445cb61   esp = 0xbfbace90   ebp = 0x3800c878
    Found by: stack scanning
60  libc-2.5.so + 0x126de1
    eip = 0x04519de2   esp = 0xbfbace98   ebp = 0x3800c878
    Found by: stack scanning
61  libc-2.5.so + 0x68ee5
    eip = 0x0445bee6   esp = 0xbfbace9c   ebp = 0x3800c878
    Found by: stack scanning
62  libc-2.5.so + 0x699e8
    eip = 0x0445c9e9   esp = 0xbfbacea8   ebp = 0x3800c878
    Found by: stack scanning
63  libxul.so!nsAutoPtr<nsINIParser_internal::INIValue>::~nsAutoPtr() [nsAutoPtr.h : 104 + 0x18]
    eip = 0x01adcf0a   esp = 0xbfbaceb0   ebp = 0x3800c878
    Found by: stack scanning
64  libpthread-2.5.so + 0xa9c4
    eip = 0x0035d9c5   esp = 0xbfbaced0   ebp = 0x3800c878
    Found by: stack scanning
65  libnspr4.so!PR_GetCurrentThread [ptthread.c : 655 + 0xd]
    eip = 0x0014c266   esp = 0xbfbacee0   ebp = 0x3800c878
    Found by: stack scanning
66  libc-2.5.so + 0x699e8
    eip = 0x0445c9e9   esp = 0xbfbacee8   ebp = 0x3800c878
    Found by: stack scanning
67  libstdc++.so.6.0.8 + 0xeed3
    eip = 0x033cced4   esp = 0xbfbacf3c   ebp = 0x3800c878
    Found by: stack scanning

Thread 1
 0  linux-gate.so + 0x402
    eip = 0x0054b402   esp = 0xb7ef60c8   ebp = 0xb7ef6128   ebx = 0x0000000e
    esi = 0xffffffff   edi = 0x00000000   eax = 0xfffffffc   ecx = 0x08dc7dd0
    edx = 0x000003ff   efl = 0x00200216
    Found by: given as instruction pointer in context
 1  0x8d8c127
    eip = 0x08d8c128   esp = 0xb7ef6130   ebp = 0xb7ef6158
    Found by: previous frame's frame pointer
 2  libxul.so!event_base_loop [event.c : 513 + 0x1b]
    eip = 0x01a438fe   esp = 0xb7ef6160   ebp = 0xb7ef6198
    Found by: previous frame's frame pointer
 3  libxul.so!base::MessagePumpLibevent::Run(base::MessagePump::Delegate*) [message_pump_libevent.cc : 330 + 0x15]
    eip = 0x01abbe5b   esp = 0xb7ef61a0   ebp = 0xb7ef61f8
    Found by: previous frame's frame pointer
 4  libxul.so!MessageLoop::RunInternal() [message_loop.cc : 216 + 0x20]
    eip = 0x01a64fb3   esp = 0xb7ef6200   ebp = 0xb7ef6228
    Found by: previous frame's frame pointer
 5  libxul.so!MessageLoop::RunHandler() [message_loop.cc : 199 + 0xa]
    eip = 0x01a64f2f   esp = 0xb7ef6230   ebp = 0xb7ef6248
    Found by: previous frame's frame pointer
 6  libxul.so!MessageLoop::Run() [message_loop.cc : 173 + 0xa]
    eip = 0x01a64eb3   esp = 0xb7ef6250   ebp = 0xb7ef6278
    Found by: previous frame's frame pointer
 7  libxul.so!base::Thread::ThreadMain() [thread.cc : 165 + 0xd]
    eip = 0x01a8a410   esp = 0xb7ef6280   ebp = 0xb7ef6388
    Found by: previous frame's frame pointer
 8  libxul.so!ThreadFunc(void*) [platform_thread_posix.cc : 26 + 0x11]
    eip = 0x01abc3e2   esp = 0xb7ef6390   ebp = 0xb7ef63b8
    Found by: previous frame's frame pointer
 9  libpthread-2.5.so + 0x5831
    eip = 0x00358832   esp = 0xb7ef63c0   ebp = 0xb7ef64a8
    Found by: previous frame's frame pointer
10  libc-2.5.so + 0xd1f6d
    eip = 0x044c4f6e   esp = 0xb7ef64b0   ebp = 0x00000000
    Found by: previous frame's frame pointer

Thread 2
 0  linux-gate.so + 0x402
    eip = 0x0054b402   esp = 0xb74f52ec   ebp = 0xb74f5338   ebx = 0x08e3dc28
    esi = 0x00000000   edi = 0x00000009   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x00000009   efl = 0x00200206
    Found by: given as instruction pointer in context
 1  libmozjs.so!JSBackgroundThread::work() [jstask.cpp : 91 + 0x15]
    eip = 0x0539c352   esp = 0xb74f5340   ebp = 0xb74f5368
    Found by: previous frame's frame pointer
 2  libmozjs.so!start(void*) [jstask.cpp : 43 + 0xa]
    eip = 0x0539c0fd   esp = 0xb74f5370   ebp = 0xb74f5388
    Found by: previous frame's frame pointer
 3  libnspr4.so!_pt_root [ptthread.c : 228 + 0x10]
    eip = 0x0014b783   esp = 0xb74f5390   ebp = 0xb74f53b8
    Found by: previous frame's frame pointer
 4  libpthread-2.5.so + 0x5831
    eip = 0x00358832   esp = 0xb74f53c0   ebp = 0xb74f54a8
    Found by: previous frame's frame pointer
 5  libc-2.5.so + 0xd1f6d
    eip = 0x044c4f6e   esp = 0xb74f54b0   ebp = 0x00000000
    Found by: previous frame's frame pointer

Thread 3
 0  linux-gate.so + 0x402
    eip = 0x0054b402   esp = 0xb6af42b0   ebp = 0xb6af4308   ebx = 0x08e3df00
    esi = 0xb6af42b8   edi = 0x0000001d   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x0000001d   efl = 0x00200216
    Found by: given as instruction pointer in context
 1  0x5a95f0f
    eip = 0x05a95f10   esp = 0xb6af4310   ebp = 0x4cd7243b
    Found by: previous frame's frame pointer
 2  libnspr4.so!PR_WaitCondVar [ptsynch.c : 419 + 0x1d]
    eip = 0x00144445   esp = 0xb6af4330   ebp = 0x4cd7243b
    Found by: stack scanning
 3  libmozjs.so!JS_TriggerOperationCallback [jsapi.cpp : 5145 + 0x12]
    eip = 0x052a8552   esp = 0xb6af4340   ebp = 0x4cd7243b
    Found by: stack scanning
 4  libxul.so!XPCJSRuntime::WatchdogMain(void*) [xpcjsruntime.cpp : 808 + 0x19]
    eip = 0x00871a9c   esp = 0xb6af4360   ebp = 0x4cd7243b
    Found by: stack scanning
 5  libpthread-2.5.so + 0xaa49
    eip = 0x0035da4a   esp = 0xb6af4370   ebp = 0x4cd7243b
    Found by: stack scanning
 6  libnspr4.so!_pt_root [ptthread.c : 228 + 0x10]
    eip = 0x0014b783   esp = 0xb6af4390   ebp = 0x4cd7243b
    Found by: stack scanning
 7  libpthread-2.5.so + 0x5831
    eip = 0x00358832   esp = 0xb6af43c0   ebp = 0x4cd7243b
    Found by: stack scanning

Thread 4
 0  linux-gate.so + 0x402
    eip = 0x0054b402   esp = 0xb56f2180   ebp = 0xb56f21d8   ebx = 0x08dcd8f8
    esi = 0xb56f2188   edi = 0x000001a7   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x000001a7   efl = 0x00200202
    Found by: given as instruction pointer in context
 1  0x32e63277
    eip = 0x32e63278   esp = 0xb56f21e0   ebp = 0x4cd7243a
    Found by: previous frame's frame pointer
 2  libnspr4.so!PR_WaitCondVar [ptsynch.c : 419 + 0x1d]
    eip = 0x00144445   esp = 0xb56f2200   ebp = 0x4cd7243a
    Found by: stack scanning
 3  libxul.so!nsTArray<nsTimerImpl*>::operator[](unsigned int) [nsTArray.h : 350 + 0x11]
    eip = 0x01b53834   esp = 0xb56f2210   ebp = 0x4cd7243a
    Found by: stack scanning
 4  libxul.so!TimerThread::Run() [TimerThread.cpp : 344 + 0x14]
    eip = 0x01b531c8   esp = 0xb56f2230   ebp = 0x4cd7243a
    Found by: stack scanning
 5  libxul.so!nsCOMPtr<nsIRunnable>* address_of<nsIRunnable>(nsCOMPtr<nsIRunnable>&) [nsCOMPtr.h : 1284 + 0xa]
    eip = 0x0095186c   esp = 0xb56f2250   ebp = 0x4cd7243a
    Found by: stack scanning
 6  libxul.so!nsThread::ProcessNextEvent(int, int*) [nsThread.cpp : 527 + 0x16]
    eip = 0x01b4ae70   esp = 0xb56f2290   ebp = 0x4cd7243a
    Found by: stack scanning
 7  libxul.so!NS_ProcessNextEvent_P(nsIThread*, int) [nsThreadUtils.cpp : 250 + 0x1f]
    eip = 0x01ae2d41   esp = 0xb56f2300   ebp = 0x4cd7243a
    Found by: stack scanning
 8  libxul.so!nsCOMPtr<nsIRunnable>::operator->() const [nsCOMPtr.h : 797 + 0xa]
    eip = 0x00b47340   esp = 0xb56f2310   ebp = 0x4cd7243a
    Found by: stack scanning
 9  libxul.so!nsCOMPtr<nsIRunnable>::operator=(nsIRunnable*) [nsCOMPtr.h : 641 + 0xa]
    eip = 0x009c197d   esp = 0xb56f2320   ebp = 0x4cd7243a
    Found by: stack scanning
10  libxul.so!nsThread::ThreadFunc(void*) [nsThread.cpp : 254 + 0x12]
    eip = 0x01b49fcb   esp = 0xb56f2340   ebp = 0x4cd7243a
    Found by: stack scanning
11  libnspr4.so!PR_Unlock [ptsynch.c : 237 + 0xa]
    eip = 0x00143d92   esp = 0xb56f2360   ebp = 0x4cd7243a
    Found by: stack scanning
12  libpthread-2.5.so + 0xaa49
    eip = 0x0035da4a   esp = 0xb56f2370   ebp = 0x4cd7243a
    Found by: stack scanning
13  libnspr4.so!_pt_root [ptthread.c : 228 + 0x10]
    eip = 0x0014b783   esp = 0xb56f2390   ebp = 0x4cd7243a
    Found by: stack scanning
14  libpthread-2.5.so + 0x5831
    eip = 0x00358832   esp = 0xb56f23c0   ebp = 0x4cd7243a
    Found by: stack scanning

Thread 5
 0  linux-gate.so + 0x402
    eip = 0x0054b402   esp = 0xb1e2d100   ebp = 0xb1e2d158   ebx = 0x094551d0
    esi = 0xb1e2d108   edi = 0x00000033   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x00000033   efl = 0x00000212
    Found by: given as instruction pointer in context
 1  0x1cd51e67
    eip = 0x1cd51e68   esp = 0xb1e2d160   ebp = 0x4cd72471
    Found by: previous frame's frame pointer
 2  libnspr4.so!PR_WaitCondVar [ptsynch.c : 419 + 0x1d]
    eip = 0x00144445   esp = 0xb1e2d180   ebp = 0x4cd72471
    Found by: stack scanning
 3  libxul.so!nsEventQueue::GetEvent(int, nsIRunnable**) [nsEventQueue.cpp : 99 + 0xa]
    eip = 0x01b48c48   esp = 0xb1e2d190   ebp = 0x4cd72471
    Found by: stack scanning
 4  libnspr4.so!PR_Wait [ptsynch.c : 614 + 0x14]
    eip = 0x00144c13   esp = 0xb1e2d1b0   ebp = 0x4cd72471
    Found by: stack scanning
 5  libxul.so!nsAutoMonitor::Wait(unsigned int) [nsAutoLock.h : 340 + 0x14]
    eip = 0x009da177   esp = 0xb1e2d1e0   ebp = 0x4cd72471
    Found by: stack scanning
 6  libxul.so!nsThreadPool::Run() [nsThreadPool.cpp : 210 + 0x11]
    eip = 0x01b4e8ed   esp = 0xb1e2d200   ebp = 0x4cd72471
    Found by: stack scanning
 7  libxul.so!nsCOMPtr<nsIRunnable>::~nsCOMPtr() [nsCOMPtr.h : 510 + 0x15]
    eip = 0x0081dcba   esp = 0xb1e2d210   ebp = 0x4cd72471
    Found by: stack scanning
 8  libxul.so!nsXPConnect::FlagSystemFilenamePrefix(char const*, int) [nsXPConnect.cpp : 2307 + 0x5]
    eip = 0x00842baf   esp = 0xb1e2d288   ebp = 0x4cd72471
    Found by: stack scanning
 9  libxul.so!nsThread::ProcessNextEvent(int, int*) [nsThread.cpp : 527 + 0x16]
    eip = 0x01b4ae70   esp = 0xb1e2d290   ebp = 0x4cd72471
    Found by: stack scanning
10  libxul.so!NS_ProcessNextEvent_P(nsIThread*, int) [nsThreadUtils.cpp : 250 + 0x1f]
    eip = 0x01ae2d41   esp = 0xb1e2d300   ebp = 0x4cd72471
    Found by: stack scanning
11  libxul.so!nsCOMPtr<nsIRunnable>::operator->() const [nsCOMPtr.h : 797 + 0xa]
    eip = 0x00b47340   esp = 0xb1e2d310   ebp = 0x4cd72471
    Found by: stack scanning
12  libxul.so!nsCOMPtr<nsIRunnable>::operator=(nsIRunnable*) [nsCOMPtr.h : 641 + 0xa]
    eip = 0x009c197d   esp = 0xb1e2d320   ebp = 0x4cd72471
    Found by: stack scanning
13  libxul.so!nsThread::ThreadFunc(void*) [nsThread.cpp : 254 + 0x12]
    eip = 0x01b49fcb   esp = 0xb1e2d340   ebp = 0x4cd72471
    Found by: stack scanning
14  libnspr4.so!PR_Unlock [ptsynch.c : 237 + 0xa]
    eip = 0x00143d92   esp = 0xb1e2d360   ebp = 0x4cd72471
    Found by: stack scanning
15  libpthread-2.5.so + 0xaa49
    eip = 0x0035da4a   esp = 0xb1e2d370   ebp = 0x4cd72471
    Found by: stack scanning
16  libnspr4.so!_pt_root [ptthread.c : 228 + 0x10]
    eip = 0x0014b783   esp = 0xb1e2d390   ebp = 0x4cd72471
    Found by: stack scanning
17  libpthread-2.5.so + 0x5831
    eip = 0x00358832   esp = 0xb1e2d3c0   ebp = 0x4cd72471
    Found by: stack scanning

Thread 6
 0  linux-gate.so + 0x402
    eip = 0x0054b402   esp = 0xae096344   ebp = 0xae096358   ebx = 0xae09637c
    esi = 0x00000000   edi = 0x04547ff4   eax = 0xfffffffc   ecx = 0x00000002
    edx = 0xffffffff   efl = 0x00200246
    Found by: given as instruction pointer in context
 1  libxul.so!google_breakpad::CrashGenerationServer::Run() [crash_generation_server.cc : 278 + 0x1a]
    eip = 0x0082e868   esp = 0xae096360   ebp = 0xae096398
    Found by: previous frame's frame pointer
 2  libxul.so!google_breakpad::CrashGenerationServer::ThreadMain(void*) [crash_generation_server.cc : 462 + 0xa]
    eip = 0x0082efb9   esp = 0xae0963a0   ebp = 0xae0963b8
    Found by: previous frame's frame pointer
 3  libpthread-2.5.so + 0x5831
    eip = 0x00358832   esp = 0xae0963c0   ebp = 0xae0964a8
    Found by: previous frame's frame pointer
 4  libc-2.5.so + 0xd1f6d
    eip = 0x044c4f6e   esp = 0xae0964b0   ebp = 0x00000000
    Found by: previous frame's frame pointer

Loaded modules:
0x00110000 - 0x00112fff  libxpcom.so  ???  (main)
0x00114000 - 0x00116fff  libplds4.so  ???
0x00118000 - 0x0011afff  libplc4.so  ???
0x0011c000 - 0x00158fff  libnspr4.so  ???
0x0015c000 - 0x00175fff  libatk-1.0.so.0.1212.0  ???
0x00178000 - 0x0018dfff  libgdk_pixbuf-2.0.so.0.1000.4  ???
0x0018f000 - 0x00196fff  libpangocairo-1.0.so.0.1400.9  ???
0x00198000 - 0x00199fff  libgmodule-2.0.so.0.1200.3  ???
0x0019b000 - 0x001a5fff  libgcc_s-4.1.2-20080825.so.1  ???
0x001a7000 - 0x001c1fff  ld-2.5.so  ???
0x001c4000 - 0x0024dfff  libgdk-x11-2.0.so.0.1000.4  ???
0x00251000 - 0x0028dfff  libpango-1.0.so.0.1400.9  ???
0x00290000 - 0x002fbfff  libcairo.so.2.9.2  ???
0x002fe000 - 0x0033bfff  libgobject-2.0.so.0.1200.3  ???
0x0033d000 - 0x00344fff  libXrender.so.1.3.0  ???
0x00346000 - 0x00349fff  libgthread-2.0.so.0.1200.3  ???
0x0034c000 - 0x0034efff  libdl-2.5.so  ???
0x00353000 - 0x00367fff  libpthread-2.5.so  ???
0x0036c000 - 0x00388fff  libnssutil3.so  ???
0x0038e000 - 0x0042afff  libglib-2.0.so.0.1200.3  ???
0x0042e000 - 0x0052cfff  libX11.so.6.2.0  ???
0x00531000 - 0x0053ffff  libXext.so.6.4.0  ???
0x00541000 - 0x00547fff  librt-2.5.so  ???
0x0054b000 - 0x0054bfff  linux-gate.so  ???
0x0054c000 - 0x020f3fff  libxul.so  ???
0x02214000 - 0x022e3fff  libsqlite3.so  ???
0x022e7000 - 0x02314fff  libsmime3.so  ???
0x02318000 - 0x02360fff  libssl3.so  ???
0x02363000 - 0x024ccfff  libnss3.so  ???
0x024d2000 - 0x024dafff  libXcursor.so.1.0.2  ???
0x024dc000 - 0x024edfff  libz.so.1.2.3  ???
0x024ef000 - 0x02505fff  libICE.so.6.3.0  ???
0x02509000 - 0x0250ffff  libpopt.so.0.0.0  ???
0x02511000 - 0x0252dfff  libdbus-glib-1.so.2.1.0  ???
0x0252f000 - 0x02543fff  libnsl-2.5.so  ???
0x02548000 - 0x02549fff  libkeyutils-1.2.so  ???
0x0254b000 - 0x0254cfff  UTF-16.so  ???
0x0254f000 - 0x02552fff  libnullplugin.so  ???
0x02554000 - 0x02574fff  libjpeg.so.62.0.0  ???
0x02576000 - 0x025a2fff  libgssapi_krb5.so.2.2  ???
0x025a4000 - 0x025c8fff  libk5crypto.so.3.1  ???
0x025ca000 - 0x025d6fff  libdbusservice.so  ???
0x025d8000 - 0x025e9fff  libmozgnome.so  ???
0x025eb000 - 0x025fefff  libimgicon.so  ???
0x02811000 - 0x02812fff  libcom_err.so.2.1  ???
0x02a7e000 - 0x02a82fff  libXdmcp.so.6.0.0  ???
0x02e7a000 - 0x02fa5fff  libxml2.so.2.6.26  ???
0x02fae000 - 0x030d7fff  libcrypto.so.0.9.8e  ???
0x030f1000 - 0x03134fff  libssl.so.0.9.8e  ???
0x0313b000 - 0x03188fff  libORBit-2.so.0.1.0  ???
0x03195000 - 0x031c7fff  libgconf-2.so.4.1.0  ???
0x031cd000 - 0x032a6fff  libasound.so.2.0.0  ???
0x032ae000 - 0x0330dfff  libgnomevfs-2.so.0.1600.2  ???
0x03313000 - 0x03314fff  libutil-2.5.so  ???
0x03319000 - 0x03327fff  libavahi-client.so.3.2.1  ???
0x0332b000 - 0x03352fff  libaudiofile.so.0.0.2  ???
0x03358000 - 0x033b1fff  libbonobo-2.so.0.0.0  ???
0x033be000 - 0x0349dfff  libstdc++.so.6.0.8  ???
0x034ab000 - 0x034aefff  libORBitCosNaming-2.so.0.1.0  ???
0x034b2000 - 0x034c5fff  libbonobo-activation.so.4.0.0  ???
0x034ca000 - 0x034defff  libgnome-2.so.0.1600.0  ???
0x034e2000 - 0x034edfff  libgnome-keyring.so.0.0.1  ???
0x034f1000 - 0x0351cfff  libgnomecanvas-2.so.0.1400.0  ???
0x03520000 - 0x03583fff  libbonoboui-2.so.0.0.0  ???
0x03589000 - 0x0359efff  libart_lgpl_2.so.2.3.17  ???
0x035a2000 - 0x03631fff  libgnomeui-2.so.0.1600.0  ???
0x03804000 - 0x0380afff  libXi.so.6.0.0  ???
0x03847000 - 0x0384afff  libpixbufloader-png.so  ???
0x0388f000 - 0x038e2fff  libXt.so.6.0.0  ???
0x03a35000 - 0x03a3cfff  libkrb5support.so.0.1  ???
0x03bee000 - 0x03bf3fff  libnotify.so.1.1.0  ???
0x03e45000 - 0x03e47fff  libcap.so.1.10  ???
0x041b8000 - 0x041b9fff  libavahi-glib.so.1.0.1  ???
0x043bf000 - 0x043c1fff  libXrandr.so.2.0.0  ???
0x043f3000 - 0x04545fff  libc-2.5.so  ???
0x045cc000 - 0x045d3fff  libSM.so.6.0.0  ???
0x04912000 - 0x04913fff  pango-basic-fc.so  ???
0x0497c000 - 0x049a8fff  libpangoft2-1.0.so.0.1400.9  ???
0x04f4e000 - 0x04f4ffff  libXss.so.1.0.0  ???
0x0527f000 - 0x05458fff  libmozjs.so  ???
0x0548c000 - 0x0551efff  libkrb5.so.3.3  ???
0x05631000 - 0x05646fff  libselinux.so.1  ???
0x057c4000 - 0x057c4fff  ISO8859-1.so  ???
0x057c5000 - 0x057c6fff  ISO8859-1.so  ???
0x05867000 - 0x0586afff  libnss_dns-2.5.so  ???
0x05b87000 - 0x05b91fff  libavahi-common.so.3.4.3  ???
0x06258000 - 0x0625bfff  libXfixes.so.3.1.0  ???
0x064b0000 - 0x064cefff  libexpat.so.0.5.0  ???
0x0669f000 - 0x066a0fff  libXau.so.6.0.0  ???
0x06bac000 - 0x06bb5fff  libnss_files-2.5.so  ???
0x0729b000 - 0x072c1fff  libfontconfig.so.1.1.0  ???
0x0735a000 - 0x07394fff  libsepol.so.1  ???
0x0754a000 - 0x0755bfff  libnkgnomevfs.so  ???
0x079d1000 - 0x079e0fff  libresolv-2.5.so  ???
0x07bd8000 - 0x07be0fff  libxfce.so  ???
0x07c5a000 - 0x07c62fff  libesd.so.0.2.36  ???
0x07c72000 - 0x07ccbfff  libfreebl3.so  ???
0x07d19000 - 0x07d55fff  libdbus-1.so.3.4.0  ???
0x07fb3000 - 0x0802ffff  libfreetype.so.6.3.10  ???
0x08048000 - 0x0804afff  firefox-bin  ???
0x0819f000 - 0x081c5fff  libm-2.5.so  ???
0x08453000 - 0x087e3fff  libgtk-x11-2.0.so.0.1000.4  ???
0x08847000 - 0x08848fff  libXinerama.so.1.0.0  ???
0x08969000 - 0x0897bfff  libbrowserdirprovider.so  ???
0x08996000 - 0x089bafff  libpng12.so.0.10.0  ???
0x08cc8000 - 0x08d1afff  libbrowsercomps.so  ???
0xae097000 - 0xaebc2fff  libflashplayer.so  ???
0xb1e2e000 - 0xb1e61fff  DejaVuLGCSerif.ttf  ???
0xb3988000 - 0xb39b0fff  LiberationSerif-Bold.ttf  ???
0xb39b1000 - 0xb39dbfff  LiberationSerif-Regular.ttf  ???
0xb39dc000 - 0xb39fffff  n021003l.pfb  ???
0xb3b01000 - 0xb3b28fff  LiberationSans-Bold.ttf  ???
0xb3b29000 - 0xb3b50fff  LiberationSans-Regular.ttf  ???
0xb3b51000 - 0xb3bbdfff  DejaVuLGCSans.ttf  ???
0xb3bbe000 - 0xb3bf7fff  DejaVuLGCSansMono.ttf  ???
0xb3bf8000 - 0xb3c64fff  DejaVuLGCSans.ttf  ???
0xb3c65000 - 0xb3c76fff  spider.jar  ???
0xb3c77000 - 0xb3d00fff  classic.jar  ???
0xb3d01000 - 0xb3f03fff  toolkit.jar  ???
0xb3f04000 - 0xb40fffff  browser.jar  ???
0xb4c02000 - 0xb4c61fff  SYSV00000000 (deleted)  ???
0xb4c62000 - 0xb4c63fff  87f5e051180a7a75f16eb6fe7dbd3749-x86.cache-2  ???
0xb4c64000 - 0xb4c69fff  b79f3aaa7d385a141ab53ec885cc22a8-x86.cache-2  ???
0xb4c6a000 - 0xb4c6cfff  b67b32625a2bb51b023d3814a918f351-x86.cache-2  ???
0xb4c6d000 - 0xb4c72fff  7ddba6133ef499da58de5e8c586d3b75-x86.cache-2  ???
0xb4c73000 - 0xb4c7afff  e19de935dec46bbf3ed114ee4965548a-x86.cache-2  ???
0xb4c7b000 - 0xb4cf1fff  en-US.jar  ???
0xb7f06000 - 0xb7f07fff  e3ead4b767b8819993a6fa3ae306afa9-x86.cache-2  ???
0xb7f08000 - 0xb7f0cfff  beeeeb3dfe132a8a0633a017c99ce0c0-x86.cache-2  ???
0xb7f0d000 - 0xb7f13fff  gconv-modules.cache  ???

 EXIT STATUS: NORMAL (7.201729 seconds)
""",
"""
Operating system: Windows NT
                  5.1.2600 Service Pack 3
CPU: x86
     GenuineIntel family 6 model 23 stepping 6
     1 CPU

Crash reason:  EXCEPTION_ACCESS_VIOLATION_WRITE
Crash address: 0x0

Thread 0 (crashed)
 0  mozjs.dll!JS_Assert [jsutil.cpp : 73 + 0x0]
    eip = 0x00821d0a   esp = 0x0012a968   ebp = 0x0012a968   ebx = 0x00000000
    esi = 0x084d9514   edi = 0xffff0001   eax = 0xffffffff   ecx = 0x32bde8d7
    edx = 0x00643d38   efl = 0x00010202
    Found by: given as instruction pointer in context
 1  mozjs.dll!js::CompartmentChecker::fail(JSCompartment *,JSCompartment *) [jscntxtinlines.h : 541 + 0x13]
    eip = 0x0069f57d   esp = 0x0012a970   ebp = 0x0012a97c
    Found by: call frame info
 2  mozjs.dll!js::CompartmentChecker::check(JSCompartment *) [jscntxtinlines.h : 549 + 0xf]
    eip = 0x006ae59b   esp = 0x0012a984   ebp = 0x0012a990
    Found by: call frame info
 3  mozjs.dll!js::CompartmentChecker::check(JSObject *) [jscntxtinlines.h : 557 + 0x10]
    eip = 0x006ae53e   esp = 0x0012a998   ebp = 0x0012a9a0
    Found by: call frame info
 4  mozjs.dll!js::assertSameCompartment<JSObject *>(JSContext *,JSObject *) [jscntxtinlines.h : 624 + 0xb]
    eip = 0x006ae771   esp = 0x0012a9a8   ebp = 0x0012a9b4
    Found by: call frame info
 5  mozjs.dll!JS_GetPrototype [jsapi.cpp : 2886 + 0xc]
    eip = 0x00696661   esp = 0x0012a9bc   ebp = 0x0012a9d4
    Found by: call frame info
 6  xul.dll!IsObjInProtoChain [nsDOMClassInfo.cpp : 9426 + 0xd]
    eip = 0x10cf45fd   esp = 0x0012a9dc   ebp = 0x0012aa04
    Found by: call frame info
 7  xul.dll!nsHTMLPluginObjElementSH::SetupProtoChain(nsIXPConnectWrappedNative *,JSContext *,JSObject *) [nsDOMClassInfo.cpp : 9514 + 0x10]
    eip = 0x10cf43d1   esp = 0x0012aa0c   ebp = 0x0012aa94
    Found by: call frame info
 8  xul.dll!nsHTMLPluginObjElementSH::PostCreate(nsIXPConnectWrappedNative *,JSContext *,JSObject *) [nsDOMClassInfo.cpp : 9606 + 0x10]
    eip = 0x10cf46a0   esp = 0x0012aa9c   ebp = 0x0012aac0
    Found by: call frame info
 9  xul.dll!FinishCreate [xpcwrappednative.cpp : 672 + 0x2e]
    eip = 0x1112c8ab   esp = 0x0012aac8   ebp = 0x0012ab28
    Found by: call frame info
10  xul.dll!XPCWrappedNative::GetNewOrUsed(XPCCallContext &,xpcObjectHelper &,XPCWrappedNativeScope *,XPCNativeInterface *,int,XPCWrappedNative * *) [xpcwrappednative.cpp : 602 + 0x21]
    eip = 0x1112bc52   esp = 0x0012ab30   ebp = 0x0012ad30
    Found by: call frame info
11  xul.dll!XPCConvert::NativeInterface2JSObject(XPCLazyCallContext &,jsval_layout *,nsIXPConnectJSObjectHolder * *,xpcObjectHelper &,nsID const *,XPCNativeInterface * *,JSObject *,int,int,unsigned int *) [xpcconvert.cpp : 1290 + 0x38]
    eip = 0x11123378   esp = 0x0012ad38   ebp = 0x0012ae44
    Found by: call frame info
12  xul.dll!NativeInterface2JSObject [nsXPConnect.cpp : 1193 + 0x28]
    eip = 0x110e6f7f   esp = 0x0012ae4c   ebp = 0x0012ae9c
    Found by: call frame info
13  xul.dll!nsXPConnect::WrapNativeToJSVal(JSContext *,JSObject *,nsISupports *,nsWrapperCache *,nsID const *,int,jsval_layout *,nsIXPConnectJSObjectHolder * *) [nsXPConnect.cpp : 1249 + 0x27]
    eip = 0x110e70db   esp = 0x0012aea4   ebp = 0x0012af88
    Found by: call frame info
14  xul.dll!nsContentUtils::WrapNative(JSContext *,JSObject *,nsISupports *,nsWrapperCache *,nsID const *,jsval_layout *,nsIXPConnectJSObjectHolder * *,int) [nsContentUtils.cpp : 5541 + 0x32]
    eip = 0x10ab7aa2   esp = 0x0012af90   ebp = 0x0012afc4
    Found by: call frame info
15  xul.dll!nsContentUtils::WrapNative(JSContext *,JSObject *,nsISupports *,nsWrapperCache *,jsval_layout *,nsIXPConnectJSObjectHolder * *,int) [nsContentUtils.h : 1616 + 0x22]
    eip = 0x10ce6926   esp = 0x0012afcc   ebp = 0x0012afec
    Found by: call frame info
16  xul.dll!nsDOMClassInfo::WrapNative(JSContext *,JSObject *,nsISupports *,nsWrapperCache *,int,jsval_layout *,nsIXPConnectJSObjectHolder * *) [nsDOMClassInfo.h : 175 + 0x20]
    eip = 0x10ce68f4   esp = 0x0012aff4   ebp = 0x0012b010
    Found by: call frame info
17  xul.dll!nsArraySH::GetProperty(nsIXPConnectWrappedNative *,JSContext *,JSObject *,jsid,jsval_layout *,int *) [nsDOMClassInfo.cpp : 7987 + 0x26]
    eip = 0x10cefef8   esp = 0x0012b018   ebp = 0x0012b058
    Found by: call frame info
18  xul.dll!nsNamedArraySH::GetProperty(nsIXPConnectWrappedNative *,JSContext *,JSObject *,jsid,jsval_layout *,int *) [nsDOMClassInfo.cpp : 8118 + 0x20]
    eip = 0x10cf0548   esp = 0x0012b060   ebp = 0x0012b0a4
    Found by: call frame info
19  xul.dll!XPC_WN_Helper_GetProperty [xpcwrappednativejsops.cpp : 979 + 0x25]
    eip = 0x1111c68e   esp = 0x0012b0ac   ebp = 0x0012b0dc
    Found by: call frame info
20  mozjs.dll!js::CallJSPropertyOp(JSContext *,int (*)(JSContext *,JSObject *,jsid,js::Value *),JSObject *,jsid,js::Value *) [jscntxtinlines.h : 728 + 0x12]
    eip = 0x00777715   esp = 0x0012b0e4   ebp = 0x0012b0f8
    Found by: call frame info
21  mozjs.dll!js::Shape::get(JSContext *,JSObject *,JSObject *,js::Value *) [jsscopeinlines.h : 256 + 0x50]
    eip = 0x0077e363   esp = 0x0012b100   ebp = 0x0012b128
    Found by: call frame info
22  mozjs.dll!js_NativeGetInline [jsobj.cpp : 4863 + 0x17]
    eip = 0x0077e0bb   esp = 0x0012b130   ebp = 0x0012b180
    Found by: call frame info
23  mozjs.dll!js_GetPropertyHelperWithShapeInline [jsobj.cpp : 5037 + 0x1c]
    eip = 0x0077ec45   esp = 0x0012b188   ebp = 0x0012b1d4
    Found by: call frame info
24  mozjs.dll!js_GetPropertyHelperInline [jsobj.cpp : 5058 + 0x24]
    eip = 0x0077eddb   esp = 0x0012b1dc   ebp = 0x0012b204
    Found by: call frame info
25  mozjs.dll!js_GetProperty(JSContext *,JSObject *,JSObject *,jsid,js::Value *) [jsobj.cpp : 5071 + 0x1a]
    eip = 0x0077ee1e   esp = 0x0012b20c   ebp = 0x0012b224
    Found by: call frame info
26  mozjs.dll!JSObject::getProperty(JSContext *,JSObject *,jsid,js::Value *) [jsobj.h : 1075 + 0x2b]
    eip = 0x00696be3   esp = 0x0012b22c   ebp = 0x0012b24c
    Found by: call frame info
27  mozjs.dll!JSWrapper::get(JSContext *,JSObject *,JSObject *,jsid,js::Value *) [jswrapper.cpp : 207 + 0x48]
    eip = 0x00822fa2   esp = 0x0012b254   ebp = 0x0012b26c
    Found by: call frame info
28  mozjs.dll!js::JSProxy::get(JSContext *,JSObject *,JSObject *,jsid,js::Value *) [jsproxy.cpp : 760 + 0x2b]
    eip = 0x007c8a42   esp = 0x0012b274   ebp = 0x0012b29c
    Found by: call frame info
29  mozjs.dll!js::proxy_GetProperty [jsproxy.cpp : 853 + 0x18]
    eip = 0x007ca42c   esp = 0x0012b2a4   ebp = 0x0012b2b8
    Found by: call frame info
30  mozjs.dll!JSObject::getProperty(JSContext *,JSObject *,jsid,js::Value *) [jsobj.h : 1075 + 0x2b]
    eip = 0x00696be3   esp = 0x0012b2c0   ebp = 0x0012b2e0
    Found by: call frame info
31  mozjs.dll!JSWrapper::get(JSContext *,JSObject *,JSObject *,jsid,js::Value *) [jswrapper.cpp : 207 + 0x48]
    eip = 0x00822fa2   esp = 0x0012b2e8   ebp = 0x0012b300
    Found by: call frame info
32  mozjs.dll!JSCrossCompartmentWrapper::get(JSContext *,JSObject *,JSObject *,jsid,js::Value *) [jswrapper.cpp : 483 + 0x85]
    eip = 0x008248c9   esp = 0x0012b308   ebp = 0x0012b394
    Found by: call frame info
33  xul.dll!xpc::CrossOriginWrapper::get(JSContext *,JSObject *,JSObject *,jsid,js::Value *) [CrossOriginWrapper.cpp : 84 + 0x1c]
    eip = 0x111f61c6   esp = 0x0012b39c   ebp = 0x0012b3b8
    Found by: call frame info
34  mozjs.dll!js::JSProxy::get(JSContext *,JSObject *,JSObject *,jsid,js::Value *) [jsproxy.cpp : 760 + 0x2b]
    eip = 0x007c8a42   esp = 0x0012b3c0   ebp = 0x0012b3e8
    Found by: call frame info
35  mozjs.dll!js::proxy_GetProperty [jsproxy.cpp : 853 + 0x18]
    eip = 0x007ca42c   esp = 0x0012b3f0   ebp = 0x0012b404
    Found by: call frame info
36  mozjs.dll!JSObject::getProperty(JSContext *,JSObject *,jsid,js::Value *) [jsobj.h : 1075 + 0x2b]
    eip = 0x00696be3   esp = 0x0012b40c   ebp = 0x0012b42c
    Found by: call frame info
37  mozjs.dll!JSObject::getProperty(JSContext *,jsid,js::Value *) [jsobj.h : 1079 + 0x17]
    eip = 0x00696b8f   esp = 0x0012b434   ebp = 0x0012b448
    Found by: call frame info
38  mozjs.dll!js::Interpret(JSContext *,JSStackFrame *,unsigned int,JSInterpMode) [jsinterp.cpp : 4513 + 0x1c]
    eip = 0x0074d6e5   esp = 0x0012b450   ebp = 0x0012c4c0
    Found by: call frame info
39  mozjs.dll!js::RunScript(JSContext *,JSScript *,JSStackFrame *) [jsinterp.cpp : 665 + 0x10]
    eip = 0x0073c71c   esp = 0x0012c4c8   ebp = 0x0012c4e8   ebx = 0x00000000
    Found by: call frame info
40  mozjs.dll!js::Invoke(JSContext *,js::CallArgs const &,unsigned int) [jsinterp.cpp : 768 + 0x10]
    eip = 0x0073cc17   esp = 0x0012c4f0   ebp = 0x0012c550
    Found by: call frame info
41  mozjs.dll!js::ExternalInvoke(JSContext *,js::Value const &,js::Value const &,unsigned int,js::Value *,js::Value *) [jsinterp.cpp : 881 + 0xe]
    eip = 0x0073dc27   esp = 0x0012c558   ebp = 0x0012c58c
    Found by: call frame info
42  mozjs.dll!js::ExternalInvoke [jsinterp.h : 954 + 0x29]
    eip = 0x0069ff30   esp = 0x0012c594   ebp = 0x0012c5b4
    Found by: call frame info
43  mozjs.dll!JS_CallFunctionValue [jsapi.cpp : 4898 + 0x37]
    eip = 0x006a0384   esp = 0x0012c5bc   ebp = 0x0012c5e8
    Found by: call frame info
44  xul.dll!nsXPCWrappedJSClass::CallMethod(nsXPCWrappedJS *,unsigned short,XPTMethodDescriptor const *,nsXPTCMiniVariant *) [xpcwrappedjsclass.cpp : 1694 + 0x34]
    eip = 0x111f0df3   esp = 0x0012c5f0   ebp = 0x0012ca4c
    Found by: call frame info
45  xul.dll!nsXPCWrappedJS::CallMethod(unsigned short,XPTMethodDescriptor const *,nsXPTCMiniVariant *) [xpcwrappedjs.cpp : 577 + 0x29]
    eip = 0x111ea09b   esp = 0x0012ca54   ebp = 0x0012ca6c
    Found by: call frame info
46  xul.dll!PrepareAndDispatch [xptcstubs.cpp : 114 + 0x20]
    eip = 0x114be186   esp = 0x0012ca74   ebp = 0x0012cb40
    Found by: call frame info
47  xul.dll!SharedStub [xptcstubs.cpp : 141 + 0x4]
    eip = 0x114bde56   esp = 0x0012cb48   ebp = 0x0012cb5c
    Found by: call frame info
48  xul.dll!nsEventListenerManager::HandleEventSubType(nsListenerStruct *,nsIDOMEventListener *,nsIDOMEvent *,nsPIDOMEventTarget *,unsigned int,nsCxPusher *) [nsEventListenerManager.cpp : 1112 + 0x11]
    eip = 0x10b58acf   esp = 0x0012cb64   ebp = 0x0012cb5c
    Found by: call frame info with scanning

Thread 1
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x01a0fce8   ebp = 0x01a0fd14   ebx = 0x00000000
    esi = 0x7c911086   edi = 0x0070002e   eax = 0x1000a88f   ecx = 0x0944ce20
    edx = 0x11e730f8   efl = 0x00000246
    Found by: given as instruction pointer in context
 1  xul.dll!base::MessagePumpForIO::GetIOItem(unsigned long,base::MessagePumpForIO::IOItem *) [message_pump_win.cc : 528 + 0x24]
    eip = 0x11511b3c   esp = 0x01a0fd1c   ebp = 0x01a0fd3c
    Found by: previous frame's frame pointer
 2  xul.dll!base::MessagePumpForIO::WaitForIOCompletion(unsigned long,base::MessagePumpForIO::IOHandler *) [message_pump_win.cc : 499 + 0xf]
    eip = 0x11511a42   esp = 0x01a0fd44   ebp = 0x01a0fd74
    Found by: call frame info
 3  xul.dll!base::MessagePumpForIO::WaitForWork() [message_pump_win.cc : 492 + 0xd]
    eip = 0x115119e3   esp = 0x01a0fd7c   ebp = 0x01a0fdb4
    Found by: call frame info
 4  xul.dll!base::MessagePumpForIO::DoRunLoop() [message_pump_win.cc : 477 + 0x7]
    eip = 0x11511928   esp = 0x01a0fdbc   ebp = 0x01a0fdc8
    Found by: call frame info
 5  xul.dll!base::MessagePumpWin::RunWithDispatcher(base::MessagePump::Delegate *,base::MessagePumpWin::Dispatcher *) [message_pump_win.cc : 52 + 0xc]
    eip = 0x11510a6f   esp = 0x01a0fdd0   ebp = 0x01a0fdec   ebx = 0x016fe550
    Found by: call frame info
 6  xul.dll!base::MessagePumpWin::Run(base::MessagePump::Delegate *) [message_pump_win.h : 78 + 0x14]
    eip = 0x11510ca5   esp = 0x01a0fdf4   ebp = 0x01a0fe00
    Found by: call frame info
 7  xul.dll!MessageLoop::RunInternal() [message_loop.cc : 219 + 0x1e]
    eip = 0x114db256   esp = 0x01a0fe08   ebp = 0x01a0fe24
    Found by: call frame info
 8  xul.dll!MessageLoop::RunHandler() [message_loop.cc : 202 + 0x7]
    eip = 0x114db192   esp = 0x01a0fe2c   ebp = 0x01a0fe5c
    Found by: call frame info
 9  xul.dll!MessageLoop::Run() [message_loop.cc : 176 + 0x7]
    eip = 0x114db073   esp = 0x01a0fe64   ebp = 0x01a0fe8c   ebx = 0x00fc113e
    Found by: call frame info
10  xul.dll!base::Thread::ThreadMain() [thread.cc : 156 + 0xa]
    eip = 0x114fc38a   esp = 0x01a0fe94   ebp = 0x01a0ffa8
    Found by: call frame info
11  xul.dll!`anonymous namespace'::ThreadFunc(void *) [platform_thread_win.cc : 26 + 0xc]
    eip = 0x1154d6a7   esp = 0x01a0ffb0   ebp = 0x01a0ffb4
    Found by: call frame info
12  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x01a0ffbc   ebp = 0x01a0ffec
    Found by: call frame info

Thread 2
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x01b0ff04   ebp = 0x01b0ff28   ebx = 0x01730918
    esi = 0x01b0ff4c   edi = 0x00340033   eax = 0x01b0fe30   ecx = 0x00000001
    edx = 0x0000007c   efl = 0x00000246
    Found by: given as instruction pointer in context
 1  xul.dll!WalkStackThread [nsStackWalk.cpp : 598 + 0xf]
    eip = 0x114bcd3e   esp = 0x01b0ff30   ebp = 0x01b0ff6c
    Found by: previous frame's frame pointer
 2  msvcr80d.dll + 0x48d0
    eip = 0x005348d1   esp = 0x01b0ff74   ebp = 0x01b0ffa8
    Found by: call frame info
 3  msvcr80d.dll + 0x4876
    eip = 0x00534877   esp = 0x01b0ffb0   ebp = 0x01b0ffb4
    Found by: previous frame's frame pointer
 4  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x01b0ffbc   ebp = 0x01b0ffec
    Found by: previous frame's frame pointer

Thread 3
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x0430fd40   ebp = 0x0430fda4   ebx = 0x01765d68
    esi = 0x00000570   edi = 0x00000000   eax = 0x0430fe34   ecx = 0x0430fe34
    edx = 0x0430fe34   efl = 0x00000297
    Found by: given as instruction pointer in context
 1  kernel32.dll + 0x2541
    eip = 0x7c802542   esp = 0x0430fdac   ebp = 0x0430fdb8
    Found by: previous frame's frame pointer
 2  nspr4.dll!_PR_MD_WAIT_CV [w95cv.c : 280 + 0x13]
    eip = 0x00bc31ff   esp = 0x0430fdc0   ebp = 0x0430fdd8
    Found by: previous frame's frame pointer
 3  nspr4.dll!_PR_WaitCondVar [prucv.c : 204 + 0x16]
    eip = 0x00bba871   esp = 0x0430fde0   ebp = 0x0430fdf4
    Found by: call frame info
 4  nspr4.dll!PR_WaitCondVar [prucv.c : 547 + 0x16]
    eip = 0x00bbb03f   esp = 0x0430fdfc   ebp = 0x0430fe10
    Found by: call frame info
 5  xul.dll!TimerThread::Run() [TimerThread.cpp : 375 + 0x10]
    eip = 0x114ac8c1   esp = 0x0430fe18   ebp = 0x0430feac
    Found by: call frame info
 6  xul.dll!nsThread::ProcessNextEvent(int,int *) [nsThread.cpp : 609 + 0x18]
    eip = 0x114ab08a   esp = 0x0430feb4   ebp = 0x0430fee8
    Found by: call frame info
 7  xul.dll!NS_ProcessNextEvent_P(nsIThread *,int) [nsThreadUtils.cpp : 250 + 0x15]
    eip = 0x10575b43   esp = 0x0430fef0   ebp = 0x0430ff04
    Found by: call frame info
 8  xul.dll!nsThread::ThreadFunc(void *) [nsThread.cpp : 277 + 0xa]
    eip = 0x114aa10e   esp = 0x0430ff0c   ebp = 0x0430ff4c
    Found by: call frame info
 9  nspr4.dll!_PR_NativeRunThread [pruthr.c : 426 + 0xe]
    eip = 0x00bbc87b   esp = 0x0430ff54   ebp = 0x0430ff5c
    Found by: call frame info
10  nspr4.dll!pr_root [w95thred.c : 122 + 0xe]
    eip = 0x00bc0f09   esp = 0x0430ff64   ebp = 0x0430ff6c
    Found by: call frame info
11  msvcr80d.dll + 0x48d0
    eip = 0x005348d1   esp = 0x0430ff74   ebp = 0x0430ffa8
    Found by: call frame info
12  msvcr80d.dll + 0x4876
    eip = 0x00534877   esp = 0x0430ffb0   ebp = 0x0430ffb4
    Found by: previous frame's frame pointer
13  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x0430ffbc   ebp = 0x0430ffec
    Found by: previous frame's frame pointer

Thread 4
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x0460ff7c   ebp = 0x0460ffb4   ebx = 0xc0000000
    esi = 0x00000000   edi = 0x71a8793c   eax = 0x71a5d2c6   ecx = 0x7c839ad8
    edx = 0x0012e24c   efl = 0x00000202
    Found by: given as instruction pointer in context
 1  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x0460ffbc   ebp = 0x0460ffec
    Found by: previous frame's frame pointer

Thread 5
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x0470cb38   ebp = 0x0470cb74   ebx = 0x7c90df4e
    esi = 0x00000000   edi = 0x00000001   eax = 0x06261460   ecx = 0x00000008
    edx = 0x00000000   efl = 0x00000202
    Found by: given as instruction pointer in context
 1  mswsock.dll + 0x5fa6
    eip = 0x71a55fa7   esp = 0x0470cb7c   ebp = 0x0470cc68
    Found by: previous frame's frame pointer
 2  ws2_32.dll + 0x314e
    eip = 0x71ab314f   esp = 0x0470cc70   ebp = 0x0470ccb8
    Found by: previous frame's frame pointer
 3  nspr4.dll!_PR_MD_PR_POLL [w32poll.c : 279 + 0x1f]
    eip = 0x00bc66e1   esp = 0x0470ccc0   ebp = 0x0470fd5c
    Found by: previous frame's frame pointer
 4  nspr4.dll!PR_Poll [prio.c : 173 + 0x10]
    eip = 0x00bb6f34   esp = 0x0470fd64   ebp = 0x0470fd70
    Found by: call frame info
 5  xul.dll!nsSocketTransportService::Poll(int,unsigned int *) [nsSocketTransportService2.cpp : 357 + 0x11]
    eip = 0x1067b652   esp = 0x0470fd78   ebp = 0x0470fda0
    Found by: call frame info
 6  xul.dll!nsSocketTransportService::DoPollIteration(int) [nsSocketTransportService2.cpp : 668 + 0xf]
    eip = 0x1067c297   esp = 0x0470fda8   ebp = 0x0470fdf0
    Found by: call frame info
 7  xul.dll!nsSocketTransportService::OnProcessNextEvent(nsIThreadInternal *,int,unsigned int) [nsSocketTransportService2.cpp : 547 + 0xc]
    eip = 0x1067be1d   esp = 0x0470fdf8   ebp = 0x0470fe00
    Found by: call frame info
 8  xul.dll!nsThread::ProcessNextEvent(int,int *) [nsThread.cpp : 576 + 0x49]
    eip = 0x114aafb8   esp = 0x0470fe08   ebp = 0x0470fe48
    Found by: call frame info
 9  xul.dll!NS_ProcessNextEvent_P(nsIThread *,int) [nsThreadUtils.cpp : 250 + 0x15]
    eip = 0x10575b43   esp = 0x0470fe50   ebp = 0x0470fe64
    Found by: call frame info
10  xul.dll!nsSocketTransportService::Run() [nsSocketTransportService2.cpp : 589 + 0xa]
    eip = 0x1067bf42   esp = 0x0470fe6c   ebp = 0x0470feac
    Found by: call frame info
11  xul.dll!nsThread::ProcessNextEvent(int,int *) [nsThread.cpp : 609 + 0x18]
    eip = 0x114ab08a   esp = 0x0470feb4   ebp = 0x0470fee8
    Found by: call frame info
12  xul.dll!NS_ProcessNextEvent_P(nsIThread *,int) [nsThreadUtils.cpp : 250 + 0x15]
    eip = 0x10575b43   esp = 0x0470fef0   ebp = 0x0470ff04
    Found by: call frame info
13  xul.dll!nsThread::ThreadFunc(void *) [nsThread.cpp : 277 + 0xa]
    eip = 0x114aa10e   esp = 0x0470ff0c   ebp = 0x0470ff4c
    Found by: call frame info
14  nspr4.dll!_PR_NativeRunThread [pruthr.c : 426 + 0xe]
    eip = 0x00bbc87b   esp = 0x0470ff54   ebp = 0x0470ff5c
    Found by: call frame info
15  nspr4.dll!pr_root [w95thred.c : 122 + 0xe]
    eip = 0x00bc0f09   esp = 0x0470ff64   ebp = 0x0470ff6c
    Found by: call frame info
16  msvcr80d.dll + 0x48d0
    eip = 0x005348d1   esp = 0x0470ff74   ebp = 0x0470ffa8
    Found by: call frame info
17  msvcr80d.dll + 0x4876
    eip = 0x00534877   esp = 0x0470ffb0   ebp = 0x0470ffb4
    Found by: previous frame's frame pointer
18  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x0470ffbc   ebp = 0x0470ffec
    Found by: previous frame's frame pointer

Thread 6
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x0480fdb0   ebp = 0x0480fe4c   ebx = 0x0480fdd8
    esi = 0x00000000   edi = 0x7ffd5000   eax = 0x76d77130   ecx = 0x7c80a095
    edx = 0x00015000   efl = 0x00000246
    Found by: given as instruction pointer in context
 1  kernel32.dll + 0xa114
    eip = 0x7c80a115   esp = 0x0480fe54   ebp = 0x0480fe68
    Found by: previous frame's frame pointer
 2  xul.dll!nsNotifyAddrListener::Run() [nsNotifyAddrListener.cpp : 192 + 0xf]
    eip = 0x1074c219   esp = 0x0480fe70   ebp = 0x0480feac
    Found by: previous frame's frame pointer
 3  xul.dll!nsThread::ProcessNextEvent(int,int *) [nsThread.cpp : 609 + 0x18]
    eip = 0x114ab08a   esp = 0x0480feb4   ebp = 0x0480fee8
    Found by: call frame info
 4  xul.dll!NS_ProcessNextEvent_P(nsIThread *,int) [nsThreadUtils.cpp : 250 + 0x15]
    eip = 0x10575b43   esp = 0x0480fef0   ebp = 0x0480ff04
    Found by: call frame info
 5  xul.dll!nsThread::ThreadFunc(void *) [nsThread.cpp : 277 + 0xa]
    eip = 0x114aa10e   esp = 0x0480ff0c   ebp = 0x0480ff4c
    Found by: call frame info
 6  nspr4.dll!_PR_NativeRunThread [pruthr.c : 426 + 0xe]
    eip = 0x00bbc87b   esp = 0x0480ff54   ebp = 0x0480ff5c
    Found by: call frame info
 7  nspr4.dll!pr_root [w95thred.c : 122 + 0xe]
    eip = 0x00bc0f09   esp = 0x0480ff64   ebp = 0x0480ff6c
    Found by: call frame info
 8  msvcr80d.dll + 0x48d0
    eip = 0x005348d1   esp = 0x0480ff74   ebp = 0x0480ffa8
    Found by: call frame info
 9  msvcr80d.dll + 0x4876
    eip = 0x00534877   esp = 0x0480ffb0   ebp = 0x0480ffb4
    Found by: previous frame's frame pointer
10  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x0480ffbc   ebp = 0x0480ffec
    Found by: previous frame's frame pointer

Thread 7
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x04e0fea8   ebp = 0x04e0ff44   ebx = 0x04e0fed0
    esi = 0x00000000   edi = 0x7ffd5000   eax = 0x77df848a   ecx = 0x00000006
    edx = 0x00000000   efl = 0x00000246
    Found by: given as instruction pointer in context
 1  advapi32.dll + 0x28630
    eip = 0x77df8631   esp = 0x04e0ff4c   ebp = 0x04e0ffb4
    Found by: previous frame's frame pointer
 2  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x04e0ffbc   ebp = 0x04e0ffec
    Found by: previous frame's frame pointer

Thread 8
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x0524fe50   ebp = 0x0524feb4   ebx = 0x043dfcd0
    esi = 0x00000468   edi = 0x00000000   eax = 0x005347f0   ecx = 0x1c4b8b00
    edx = 0x00000684   efl = 0x00000246
    Found by: given as instruction pointer in context
 1  kernel32.dll + 0x2541
    eip = 0x7c802542   esp = 0x0524febc   ebp = 0x0524fec8
    Found by: previous frame's frame pointer
 2  nspr4.dll!_PR_MD_WAIT_CV [w95cv.c : 280 + 0x13]
    eip = 0x00bc31ff   esp = 0x0524fed0   ebp = 0x0524fee8
    Found by: previous frame's frame pointer
 3  nspr4.dll!_PR_WaitCondVar [prucv.c : 204 + 0x16]
    eip = 0x00bba871   esp = 0x0524fef0   ebp = 0x0524ff04
    Found by: call frame info
 4  nspr4.dll!PR_WaitCondVar [prucv.c : 547 + 0x16]
    eip = 0x00bbb03f   esp = 0x0524ff0c   ebp = 0x0524ff20
    Found by: call frame info
 5  mozjs.dll!js::GCHelperThread::threadLoop(JSRuntime *) [jsgc.cpp : 1995 + 0xe]
    eip = 0x007200da   esp = 0x0524ff28   ebp = 0x0524ff3c
    Found by: call frame info
 6  mozjs.dll!js::GCHelperThread::threadMain(void *) [jsgc.cpp : 1981 + 0x11]
    eip = 0x0072008c   esp = 0x0524ff44   ebp = 0x0524ff4c
    Found by: call frame info
 7  nspr4.dll!_PR_NativeRunThread [pruthr.c : 426 + 0xe]
    eip = 0x00bbc87b   esp = 0x0524ff54   ebp = 0x0524ff5c
    Found by: call frame info
 8  nspr4.dll!pr_root [w95thred.c : 122 + 0xe]
    eip = 0x00bc0f09   esp = 0x0524ff64   ebp = 0x0524ff6c
    Found by: call frame info
 9  msvcr80d.dll + 0x48d0
    eip = 0x005348d1   esp = 0x0524ff74   ebp = 0x0524ffa8
    Found by: call frame info
10  msvcr80d.dll + 0x4876
    eip = 0x00534877   esp = 0x0524ffb0   ebp = 0x0524ffb4
    Found by: previous frame's frame pointer
11  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x0524ffbc   ebp = 0x0524ffec
    Found by: previous frame's frame pointer

Thread 9
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x0534fe4c   ebp = 0x0534feb0   ebx = 0x044115a8
    esi = 0x00000474   edi = 0x00000000   eax = 0x005347f0   ecx = 0x00000000
    edx = 0x009b28b7   efl = 0x00000297
    Found by: given as instruction pointer in context
 1  kernel32.dll + 0x2541
    eip = 0x7c802542   esp = 0x0534feb8   ebp = 0x0534fec4
    Found by: previous frame's frame pointer
 2  nspr4.dll!_PR_MD_WAIT_CV [w95cv.c : 280 + 0x13]
    eip = 0x00bc31ff   esp = 0x0534fecc   ebp = 0x0534fee4
    Found by: previous frame's frame pointer
 3  nspr4.dll!_PR_WaitCondVar [prucv.c : 204 + 0x16]
    eip = 0x00bba871   esp = 0x0534feec   ebp = 0x0534ff00
    Found by: call frame info
 4  nspr4.dll!PR_WaitCondVar [prucv.c : 547 + 0x16]
    eip = 0x00bbb03f   esp = 0x0534ff08   ebp = 0x0534ff1c
    Found by: call frame info
 5  xul.dll!XPCJSRuntime::WatchdogMain(void *) [xpcjsruntime.cpp : 861 + 0x13]
    eip = 0x1111317a   esp = 0x0534ff24   ebp = 0x0534ff4c
    Found by: call frame info
 6  nspr4.dll!_PR_NativeRunThread [pruthr.c : 426 + 0xe]
    eip = 0x00bbc87b   esp = 0x0534ff54   ebp = 0x0534ff5c
    Found by: call frame info
 7  nspr4.dll!pr_root [w95thred.c : 122 + 0xe]
    eip = 0x00bc0f09   esp = 0x0534ff64   ebp = 0x0534ff6c
    Found by: call frame info
 8  msvcr80d.dll + 0x48d0
    eip = 0x005348d1   esp = 0x0534ff74   ebp = 0x0534ffa8
    Found by: call frame info
 9  msvcr80d.dll + 0x4876
    eip = 0x00534877   esp = 0x0534ffb0   ebp = 0x0534ffb4
    Found by: previous frame's frame pointer
10  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x0534ffbc   ebp = 0x0534ffec
    Found by: previous frame's frame pointer

Thread 10
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x06bdfe18   ebp = 0x06bdff80   ebx = 0x00000000
    esi = 0x00153b80   edi = 0x00000100   eax = 0x00000000   ecx = 0x001692a8
    edx = 0xffffffff   efl = 0x00000246
    Found by: given as instruction pointer in context
 1  rpcrt4.dll + 0x6cae
    eip = 0x77e76caf   esp = 0x06bdff88   ebp = 0x06bdff88
    Found by: previous frame's frame pointer
 2  rpcrt4.dll + 0x6ad0
    eip = 0x77e76ad1   esp = 0x06bdff90   ebp = 0x06bdffa8
    Found by: previous frame's frame pointer
 3  rpcrt4.dll + 0x6c96
    eip = 0x77e76c97   esp = 0x06bdffb0   ebp = 0x06bdffb4
    Found by: previous frame's frame pointer
 4  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x06bdffbc   ebp = 0x06bdffec
    Found by: previous frame's frame pointer

Thread 11
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x06cdff20   ebp = 0x06cdff78   ebx = 0x00007530
    esi = 0x00000000   edi = 0x06cdff50   eax = 0x774fe4df   ecx = 0x7ffd5000
    edx = 0x00000000   efl = 0x00000206
    Found by: given as instruction pointer in context
 1  kernel32.dll + 0x2454
    eip = 0x7c802455   esp = 0x06cdff80   ebp = 0x06cdff88
    Found by: previous frame's frame pointer
 2  ole32.dll + 0x1e3d2
    eip = 0x774fe3d3   esp = 0x06cdff90   ebp = 0x06cdffb4
    Found by: previous frame's frame pointer
 3  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x06cdffbc   ebp = 0x06cdffec
    Found by: previous frame's frame pointer

Thread 12
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x06ddfd74   ebp = 0x06ddfdd8   ebx = 0x0612afb0
    esi = 0x00000428   edi = 0x00000000   eax = 0x00000078   ecx = 0x087e8940
    edx = 0x087e8940   efl = 0x00000246
    Found by: given as instruction pointer in context
 1  kernel32.dll + 0x2541
    eip = 0x7c802542   esp = 0x06ddfde0   ebp = 0x06ddfdec
    Found by: previous frame's frame pointer
 2  nspr4.dll!_PR_MD_WAIT_CV [w95cv.c : 280 + 0x13]
    eip = 0x00bc31ff   esp = 0x06ddfdf4   ebp = 0x06ddfe0c
    Found by: previous frame's frame pointer
 3  nspr4.dll!_PR_WaitCondVar [prucv.c : 204 + 0x16]
    eip = 0x00bba871   esp = 0x06ddfe14   ebp = 0x06ddfe28
    Found by: call frame info
 4  nspr4.dll!PR_Wait [prmon.c : 184 + 0x1c]
    eip = 0x00bba0e3   esp = 0x06ddfe30   ebp = 0x06ddfe4c
    Found by: call frame info
 5  xul.dll!nsAutoMonitor::Wait(unsigned int) [nsAutoLock.h : 346 + 0x10]
    eip = 0x1071b138   esp = 0x06ddfe54   ebp = 0x06ddfe60
    Found by: call frame info
 6  xul.dll!nsEventQueue::GetEvent(int,nsIRunnable * *) [nsEventQueue.cpp : 85 + 0x9]
    eip = 0x114a99ab   esp = 0x06ddfe68   ebp = 0x06ddfe94
    Found by: call frame info
 7  xul.dll!nsThread::nsChainedEventQueue::GetEvent(int,nsIRunnable * *) [nsThread.h : 112 + 0x12]
    eip = 0x114aa27a   esp = 0x06ddfe9c   ebp = 0x06ddfea8
    Found by: call frame info
 8  xul.dll!nsThread::ProcessNextEvent(int,int *) [nsThread.cpp : 592 + 0x48]
    eip = 0x114ab01f   esp = 0x06ddfeb0   ebp = 0x06ddfee8
    Found by: call frame info
 9  xul.dll!NS_ProcessNextEvent_P(nsIThread *,int) [nsThreadUtils.cpp : 250 + 0x15]
    eip = 0x10575b43   esp = 0x06ddfef0   ebp = 0x06ddff04
    Found by: call frame info
10  xul.dll!nsThread::ThreadFunc(void *) [nsThread.cpp : 277 + 0xa]
    eip = 0x114aa10e   esp = 0x06ddff0c   ebp = 0x06ddff4c
    Found by: call frame info
11  nspr4.dll!_PR_NativeRunThread [pruthr.c : 426 + 0xe]
    eip = 0x00bbc87b   esp = 0x06ddff54   ebp = 0x06ddff5c
    Found by: call frame info
12  nspr4.dll!pr_root [w95thred.c : 122 + 0xe]
    eip = 0x00bc0f09   esp = 0x06ddff64   ebp = 0x06ddff6c
    Found by: call frame info
13  msvcr80d.dll + 0x48d0
    eip = 0x005348d1   esp = 0x06ddff74   ebp = 0x06ddffa8
    Found by: call frame info
14  msvcr80d.dll + 0x4876
    eip = 0x00534877   esp = 0x06ddffb0   ebp = 0x06ddffb4
    Found by: previous frame's frame pointer
15  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x06ddffbc   ebp = 0x06ddffec
    Found by: previous frame's frame pointer

Thread 13
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x0700fd74   ebp = 0x0700fdd8   ebx = 0x05b25038
    esi = 0x0000040c   edi = 0x00000000   eax = 0x062d0970   ecx = 0x00000003
    edx = 0x0000002e   efl = 0x00000246
    Found by: given as instruction pointer in context
 1  kernel32.dll + 0x2541
    eip = 0x7c802542   esp = 0x0700fde0   ebp = 0x0700fdec
    Found by: previous frame's frame pointer
 2  nspr4.dll!_PR_MD_WAIT_CV [w95cv.c : 280 + 0x13]
    eip = 0x00bc31ff   esp = 0x0700fdf4   ebp = 0x0700fe0c
    Found by: previous frame's frame pointer
 3  nspr4.dll!_PR_WaitCondVar [prucv.c : 204 + 0x16]
    eip = 0x00bba871   esp = 0x0700fe14   ebp = 0x0700fe28
    Found by: call frame info
 4  nspr4.dll!PR_Wait [prmon.c : 184 + 0x1c]
    eip = 0x00bba0e3   esp = 0x0700fe30   ebp = 0x0700fe4c
    Found by: call frame info
 5  xul.dll!nsAutoMonitor::Wait(unsigned int) [nsAutoLock.h : 346 + 0x10]
    eip = 0x1071b138   esp = 0x0700fe54   ebp = 0x0700fe60
    Found by: call frame info
 6  xul.dll!nsEventQueue::GetEvent(int,nsIRunnable * *) [nsEventQueue.cpp : 85 + 0x9]
    eip = 0x114a99ab   esp = 0x0700fe68   ebp = 0x0700fe94
    Found by: call frame info
 7  xul.dll!nsThread::nsChainedEventQueue::GetEvent(int,nsIRunnable * *) [nsThread.h : 112 + 0x12]
    eip = 0x114aa27a   esp = 0x0700fe9c   ebp = 0x0700fea8
    Found by: call frame info
 8  xul.dll!nsThread::ProcessNextEvent(int,int *) [nsThread.cpp : 592 + 0x48]
    eip = 0x114ab01f   esp = 0x0700feb0   ebp = 0x0700fee8
    Found by: call frame info
 9  xul.dll!NS_ProcessNextEvent_P(nsIThread *,int) [nsThreadUtils.cpp : 250 + 0x15]
    eip = 0x10575b43   esp = 0x0700fef0   ebp = 0x0700ff04
    Found by: call frame info
10  xul.dll!nsThread::ThreadFunc(void *) [nsThread.cpp : 277 + 0xa]
    eip = 0x114aa10e   esp = 0x0700ff0c   ebp = 0x0700ff4c
    Found by: call frame info
11  nspr4.dll!_PR_NativeRunThread [pruthr.c : 426 + 0xe]
    eip = 0x00bbc87b   esp = 0x0700ff54   ebp = 0x0700ff5c
    Found by: call frame info
12  nspr4.dll!pr_root [w95thred.c : 122 + 0xe]
    eip = 0x00bc0f09   esp = 0x0700ff64   ebp = 0x0700ff6c
    Found by: call frame info
13  msvcr80d.dll + 0x48d0
    eip = 0x005348d1   esp = 0x0700ff74   ebp = 0x0700ffa8
    Found by: call frame info
14  msvcr80d.dll + 0x4876
    eip = 0x00534877   esp = 0x0700ffb0   ebp = 0x0700ffb4
    Found by: previous frame's frame pointer
15  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x0700ffbc   ebp = 0x0700ffec
    Found by: previous frame's frame pointer

Thread 14
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x0725fe08   ebp = 0x0725fe6c   ebx = 0x06406410
    esi = 0x0000044c   edi = 0x00000000   eax = 0x07ee0000   ecx = 0x0725fbd0
    edx = 0x00001000   efl = 0x00000297
    Found by: given as instruction pointer in context
 1  kernel32.dll + 0x2541
    eip = 0x7c802542   esp = 0x0725fe74   ebp = 0x0725fe80
    Found by: previous frame's frame pointer
 2  nspr4.dll!_PR_MD_WAIT_CV [w95cv.c : 280 + 0x13]
    eip = 0x00bc31ff   esp = 0x0725fe88   ebp = 0x0725fea0
    Found by: previous frame's frame pointer
 3  nspr4.dll!_PR_WaitCondVar [prucv.c : 204 + 0x16]
    eip = 0x00bba871   esp = 0x0725fea8   ebp = 0x0725febc
    Found by: call frame info
 4  nspr4.dll!PR_WaitCondVar [prucv.c : 547 + 0x16]
    eip = 0x00bbb03f   esp = 0x0725fec4   ebp = 0x0725fed8
    Found by: call frame info
 5  xul.dll!nsHostResolver::GetHostToLookup(nsHostRecord * *) [nsHostResolver.cpp : 777 + 0x10]
    eip = 0x106ac47c   esp = 0x0725fee0   ebp = 0x0725ff2c
    Found by: call frame info
 6  xul.dll!nsHostResolver::ThreadFunc(void *) [nsHostResolver.cpp : 881 + 0xb]
    eip = 0x106ac7a5   esp = 0x0725ff34   ebp = 0x0725ff4c
    Found by: call frame info
 7  nspr4.dll!_PR_NativeRunThread [pruthr.c : 426 + 0xe]
    eip = 0x00bbc87b   esp = 0x0725ff54   ebp = 0x0725ff5c
    Found by: call frame info
 8  nspr4.dll!pr_root [w95thred.c : 122 + 0xe]
    eip = 0x00bc0f09   esp = 0x0725ff64   ebp = 0x0725ff6c
    Found by: call frame info
 9  msvcr80d.dll + 0x48d0
    eip = 0x005348d1   esp = 0x0725ff74   ebp = 0x0725ffa8
    Found by: call frame info
10  msvcr80d.dll + 0x4876
    eip = 0x00534877   esp = 0x0725ffb0   ebp = 0x0725ffb4
    Found by: previous frame's frame pointer
11  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x0725ffbc   ebp = 0x0725ffec
    Found by: previous frame's frame pointer

Thread 15
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x0735fd74   ebp = 0x0735fdd8   ebx = 0x0640bac0
    esi = 0x000003b8   edi = 0x00000000   eax = 0x07ed485c   ecx = 0x00000005
    edx = 0x064338b0   efl = 0x00000246
    Found by: given as instruction pointer in context
 1  kernel32.dll + 0x2541
    eip = 0x7c802542   esp = 0x0735fde0   ebp = 0x0735fdec
    Found by: previous frame's frame pointer
 2  nspr4.dll!_PR_MD_WAIT_CV [w95cv.c : 280 + 0x13]
    eip = 0x00bc31ff   esp = 0x0735fdf4   ebp = 0x0735fe0c
    Found by: previous frame's frame pointer
 3  nspr4.dll!_PR_WaitCondVar [prucv.c : 204 + 0x16]
    eip = 0x00bba871   esp = 0x0735fe14   ebp = 0x0735fe28
    Found by: call frame info
 4  nspr4.dll!PR_Wait [prmon.c : 184 + 0x1c]
    eip = 0x00bba0e3   esp = 0x0735fe30   ebp = 0x0735fe4c
    Found by: call frame info
 5  xul.dll!nsAutoMonitor::Wait(unsigned int) [nsAutoLock.h : 346 + 0x10]
    eip = 0x1071b138   esp = 0x0735fe54   ebp = 0x0735fe60
    Found by: call frame info
 6  xul.dll!nsEventQueue::GetEvent(int,nsIRunnable * *) [nsEventQueue.cpp : 85 + 0x9]
    eip = 0x114a99ab   esp = 0x0735fe68   ebp = 0x0735fe94
    Found by: call frame info
 7  xul.dll!nsThread::nsChainedEventQueue::GetEvent(int,nsIRunnable * *) [nsThread.h : 112 + 0x12]
    eip = 0x114aa27a   esp = 0x0735fe9c   ebp = 0x0735fea8
    Found by: call frame info
 8  xul.dll!nsThread::ProcessNextEvent(int,int *) [nsThread.cpp : 592 + 0x48]
    eip = 0x114ab01f   esp = 0x0735feb0   ebp = 0x0735fee8
    Found by: call frame info
 9  xul.dll!NS_ProcessNextEvent_P(nsIThread *,int) [nsThreadUtils.cpp : 250 + 0x15]
    eip = 0x10575b43   esp = 0x0735fef0   ebp = 0x0735ff04
    Found by: call frame info
10  xul.dll!nsThread::ThreadFunc(void *) [nsThread.cpp : 277 + 0xa]
    eip = 0x114aa10e   esp = 0x0735ff0c   ebp = 0x0735ff4c
    Found by: call frame info
11  nspr4.dll!_PR_NativeRunThread [pruthr.c : 426 + 0xe]
    eip = 0x00bbc87b   esp = 0x0735ff54   ebp = 0x0735ff5c
    Found by: call frame info
12  nspr4.dll!pr_root [w95thred.c : 122 + 0xe]
    eip = 0x00bc0f09   esp = 0x0735ff64   ebp = 0x0735ff6c
    Found by: call frame info
13  msvcr80d.dll + 0x48d0
    eip = 0x005348d1   esp = 0x0735ff74   ebp = 0x0735ffa8
    Found by: call frame info
14  msvcr80d.dll + 0x4876
    eip = 0x00534877   esp = 0x0735ffb0   ebp = 0x0735ffb4
    Found by: previous frame's frame pointer
15  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x0735ffbc   ebp = 0x0735ffec
    Found by: previous frame's frame pointer

Thread 16
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x0745fd74   ebp = 0x0745fdd8   ebx = 0x064695c8
    esi = 0x00000394   edi = 0x00000000   eax = 0x106f01e0   ecx = 0x08797b28
    edx = 0x11fb3288   efl = 0x00000246
    Found by: given as instruction pointer in context
 1  kernel32.dll + 0x2541
    eip = 0x7c802542   esp = 0x0745fde0   ebp = 0x0745fdec
    Found by: previous frame's frame pointer
 2  nspr4.dll!_PR_MD_WAIT_CV [w95cv.c : 280 + 0x13]
    eip = 0x00bc31ff   esp = 0x0745fdf4   ebp = 0x0745fe0c
    Found by: previous frame's frame pointer
 3  nspr4.dll!_PR_WaitCondVar [prucv.c : 204 + 0x16]
    eip = 0x00bba871   esp = 0x0745fe14   ebp = 0x0745fe28
    Found by: call frame info
 4  nspr4.dll!PR_Wait [prmon.c : 184 + 0x1c]
    eip = 0x00bba0e3   esp = 0x0745fe30   ebp = 0x0745fe4c
    Found by: call frame info
 5  xul.dll!nsAutoMonitor::Wait(unsigned int) [nsAutoLock.h : 346 + 0x10]
    eip = 0x1071b138   esp = 0x0745fe54   ebp = 0x0745fe60
    Found by: call frame info
 6  xul.dll!nsEventQueue::GetEvent(int,nsIRunnable * *) [nsEventQueue.cpp : 85 + 0x9]
    eip = 0x114a99ab   esp = 0x0745fe68   ebp = 0x0745fe94
    Found by: call frame info
 7  xul.dll!nsThread::nsChainedEventQueue::GetEvent(int,nsIRunnable * *) [nsThread.h : 112 + 0x12]
    eip = 0x114aa27a   esp = 0x0745fe9c   ebp = 0x0745fea8
    Found by: call frame info
 8  xul.dll!nsThread::ProcessNextEvent(int,int *) [nsThread.cpp : 592 + 0x48]
    eip = 0x114ab01f   esp = 0x0745feb0   ebp = 0x0745fee8
    Found by: call frame info
 9  xul.dll!NS_ProcessNextEvent_P(nsIThread *,int) [nsThreadUtils.cpp : 250 + 0x15]
    eip = 0x10575b43   esp = 0x0745fef0   ebp = 0x0745ff04
    Found by: call frame info
10  xul.dll!nsThread::ThreadFunc(void *) [nsThread.cpp : 277 + 0xa]
    eip = 0x114aa10e   esp = 0x0745ff0c   ebp = 0x0745ff4c
    Found by: call frame info
11  nspr4.dll!_PR_NativeRunThread [pruthr.c : 426 + 0xe]
    eip = 0x00bbc87b   esp = 0x0745ff54   ebp = 0x0745ff5c
    Found by: call frame info
12  nspr4.dll!pr_root [w95thred.c : 122 + 0xe]
    eip = 0x00bc0f09   esp = 0x0745ff64   ebp = 0x0745ff6c
    Found by: call frame info
13  msvcr80d.dll + 0x48d0
    eip = 0x005348d1   esp = 0x0745ff74   ebp = 0x0745ffa8
    Found by: call frame info
14  msvcr80d.dll + 0x4876
    eip = 0x00534877   esp = 0x0745ffb0   ebp = 0x0745ffb4
    Found by: previous frame's frame pointer
15  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x0745ffbc   ebp = 0x0745ffec
    Found by: previous frame's frame pointer

Thread 17
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x0776fde4   ebp = 0x0776fe48   ebx = 0x064d8f28
    esi = 0x000002e0   edi = 0x00000000   eax = 0x10010e92   ecx = 0x064d8b00
    edx = 0x11d18d18   efl = 0x00000246
    Found by: given as instruction pointer in context
 1  kernel32.dll + 0x2541
    eip = 0x7c802542   esp = 0x0776fe50   ebp = 0x0776fe5c
    Found by: previous frame's frame pointer
 2  nspr4.dll!_PR_MD_WAIT_CV [w95cv.c : 280 + 0x13]
    eip = 0x00bc31ff   esp = 0x0776fe64   ebp = 0x0776fe7c
    Found by: previous frame's frame pointer
 3  nspr4.dll!_PR_WaitCondVar [prucv.c : 204 + 0x16]
    eip = 0x00bba871   esp = 0x0776fe84   ebp = 0x0776fe98
    Found by: call frame info
 4  nspr4.dll!PR_WaitCondVar [prucv.c : 547 + 0x16]
    eip = 0x00bbb03f   esp = 0x0776fea0   ebp = 0x0776feb4
    Found by: call frame info
 5  xul.dll!nsSSLThread::Run() [nsSSLThread.cpp : 980 + 0xe]
    eip = 0x1014af3b   esp = 0x0776febc   ebp = 0x0776ff40
    Found by: call frame info
 6  xul.dll!nsPSMBackgroundThread::nsThreadRunner(void *) [nsPSMBackgroundThread.cpp : 44 + 0xb]
    eip = 0x10149226   esp = 0x0776ff48   ebp = 0x0776ff4c
    Found by: call frame info
 7  nspr4.dll!_PR_NativeRunThread [pruthr.c : 426 + 0xe]
    eip = 0x00bbc87b   esp = 0x0776ff54   ebp = 0x0776ff5c
    Found by: call frame info
 8  nspr4.dll!pr_root [w95thred.c : 122 + 0xe]
    eip = 0x00bc0f09   esp = 0x0776ff64   ebp = 0x0776ff6c
    Found by: call frame info
 9  msvcr80d.dll + 0x48d0
    eip = 0x005348d1   esp = 0x0776ff74   ebp = 0x0776ffa8
    Found by: call frame info
10  msvcr80d.dll + 0x4876
    eip = 0x00534877   esp = 0x0776ffb0   ebp = 0x0776ffb4
    Found by: previous frame's frame pointer
11  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x0776ffbc   ebp = 0x0776ffec
    Found by: previous frame's frame pointer

Thread 18
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x0786fe04   ebp = 0x0786fe68   ebx = 0x064d95b8
    esi = 0x000002dc   edi = 0x00000000   eax = 0x064d9168   ecx = 0x064d9168
    edx = 0x11d190a4   efl = 0x00000246
    Found by: given as instruction pointer in context
 1  kernel32.dll + 0x2541
    eip = 0x7c802542   esp = 0x0786fe70   ebp = 0x0786fe7c
    Found by: previous frame's frame pointer
 2  nspr4.dll!_PR_MD_WAIT_CV [w95cv.c : 280 + 0x13]
    eip = 0x00bc31ff   esp = 0x0786fe84   ebp = 0x0786fe9c
    Found by: previous frame's frame pointer
 3  nspr4.dll!_PR_WaitCondVar [prucv.c : 204 + 0x16]
    eip = 0x00bba871   esp = 0x0786fea4   ebp = 0x0786feb8
    Found by: call frame info
 4  nspr4.dll!PR_WaitCondVar [prucv.c : 547 + 0x16]
    eip = 0x00bbb03f   esp = 0x0786fec0   ebp = 0x0786fed4
    Found by: call frame info
 5  xul.dll!nsCertVerificationThread::Run() [nsCertVerificationThread.cpp : 138 + 0xe]
    eip = 0x1014bbba   esp = 0x0786fedc   ebp = 0x0786ff40
    Found by: call frame info
 6  xul.dll!nsPSMBackgroundThread::nsThreadRunner(void *) [nsPSMBackgroundThread.cpp : 44 + 0xb]
    eip = 0x10149226   esp = 0x0786ff48   ebp = 0x0786ff4c
    Found by: call frame info
 7  nspr4.dll!_PR_NativeRunThread [pruthr.c : 426 + 0xe]
    eip = 0x00bbc87b   esp = 0x0786ff54   ebp = 0x0786ff5c
    Found by: call frame info
 8  nspr4.dll!pr_root [w95thred.c : 122 + 0xe]
    eip = 0x00bc0f09   esp = 0x0786ff64   ebp = 0x0786ff6c
    Found by: call frame info
 9  msvcr80d.dll + 0x48d0
    eip = 0x005348d1   esp = 0x0786ff74   ebp = 0x0786ffa8
    Found by: call frame info
10  msvcr80d.dll + 0x4876
    eip = 0x00534877   esp = 0x0786ffb0   ebp = 0x0786ffb4
    Found by: previous frame's frame pointer
11  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x0786ffbc   ebp = 0x0786ffec
    Found by: previous frame's frame pointer

Thread 19
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x0796fd74   ebp = 0x0796fdd8   ebx = 0x064daa50
    esi = 0x000002d8   edi = 0x00000000   eax = 0x0863b340   ecx = 0x00000002
    edx = 0x00000028   efl = 0x00000246
    Found by: given as instruction pointer in context
 1  kernel32.dll + 0x2541
    eip = 0x7c802542   esp = 0x0796fde0   ebp = 0x0796fdec
    Found by: previous frame's frame pointer
 2  nspr4.dll!_PR_MD_WAIT_CV [w95cv.c : 280 + 0x13]
    eip = 0x00bc31ff   esp = 0x0796fdf4   ebp = 0x0796fe0c
    Found by: previous frame's frame pointer
 3  nspr4.dll!_PR_WaitCondVar [prucv.c : 204 + 0x16]
    eip = 0x00bba871   esp = 0x0796fe14   ebp = 0x0796fe28
    Found by: call frame info
 4  nspr4.dll!PR_Wait [prmon.c : 184 + 0x1c]
    eip = 0x00bba0e3   esp = 0x0796fe30   ebp = 0x0796fe4c
    Found by: call frame info
 5  xul.dll!nsAutoMonitor::Wait(unsigned int) [nsAutoLock.h : 346 + 0x10]
    eip = 0x1071b138   esp = 0x0796fe54   ebp = 0x0796fe60
    Found by: call frame info
 6  xul.dll!nsEventQueue::GetEvent(int,nsIRunnable * *) [nsEventQueue.cpp : 85 + 0x9]
    eip = 0x114a99ab   esp = 0x0796fe68   ebp = 0x0796fe94
    Found by: call frame info
 7  xul.dll!nsThread::nsChainedEventQueue::GetEvent(int,nsIRunnable * *) [nsThread.h : 112 + 0x12]
    eip = 0x114aa27a   esp = 0x0796fe9c   ebp = 0x0796fea8
    Found by: call frame info
 8  xul.dll!nsThread::ProcessNextEvent(int,int *) [nsThread.cpp : 592 + 0x48]
    eip = 0x114ab01f   esp = 0x0796feb0   ebp = 0x0796fee8
    Found by: call frame info
 9  xul.dll!NS_ProcessNextEvent_P(nsIThread *,int) [nsThreadUtils.cpp : 250 + 0x15]
    eip = 0x10575b43   esp = 0x0796fef0   ebp = 0x0796ff04
    Found by: call frame info
10  xul.dll!nsThread::ThreadFunc(void *) [nsThread.cpp : 277 + 0xa]
    eip = 0x114aa10e   esp = 0x0796ff0c   ebp = 0x0796ff4c
    Found by: call frame info
11  nspr4.dll!_PR_NativeRunThread [pruthr.c : 426 + 0xe]
    eip = 0x00bbc87b   esp = 0x0796ff54   ebp = 0x0796ff5c
    Found by: call frame info
12  nspr4.dll!pr_root [w95thred.c : 122 + 0xe]
    eip = 0x00bc0f09   esp = 0x0796ff64   ebp = 0x0796ff6c
    Found by: call frame info
13  msvcr80d.dll + 0x48d0
    eip = 0x005348d1   esp = 0x0796ff74   ebp = 0x0796ffa8
    Found by: call frame info
14  msvcr80d.dll + 0x4876
    eip = 0x00534877   esp = 0x0796ffb0   ebp = 0x0796ffb4
    Found by: previous frame's frame pointer
15  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x0796ffbc   ebp = 0x0796ffec
    Found by: previous frame's frame pointer

Thread 20
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x08c2fcec   ebp = 0x08c2ffb4   ebx = 0x00000000
    esi = 0x00000000   edi = 0x00000001   eax = 0x000000c0   ecx = 0xfdfdfdfd
    edx = 0xfdfdfdfd   efl = 0x00000246
    Found by: given as instruction pointer in context
 1  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x08c2ffbc   ebp = 0x08c2ffec
    Found by: previous frame's frame pointer

Thread 21
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x08d4ff9c   ebp = 0x08d4ffb4   ebx = 0x00000000
    esi = 0x00000000   edi = 0x00000000   eax = 0x7c927edb   ecx = 0x00000000
    edx = 0x00000000   efl = 0x00000246
    Found by: given as instruction pointer in context
 1  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x08d4ffbc   ebp = 0x08d4ffec
    Found by: previous frame's frame pointer

Thread 22
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x08e4ff70   ebp = 0x08e4ffb4   ebx = 0x00000000
    esi = 0x7c97e420   edi = 0x7c97e440   eax = 0x7c910250   ecx = 0x00000000
    edx = 0x00000000   efl = 0x00000286
    Found by: given as instruction pointer in context
 1  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x08e4ffbc   ebp = 0x08e4ffec
    Found by: previous frame's frame pointer

Thread 23
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x0910fd34   ebp = 0x0910fd98   ebx = 0x080df760
    esi = 0x000001cc   edi = 0x00000000   eax = 0x0214561b   ecx = 0x0214561b
    edx = 0x00255639   efl = 0x00000297
    Found by: given as instruction pointer in context
 1  kernel32.dll + 0x2541
    eip = 0x7c802542   esp = 0x0910fda0   ebp = 0x0910fdac
    Found by: previous frame's frame pointer
 2  nspr4.dll!_PR_MD_WAIT_CV [w95cv.c : 280 + 0x13]
    eip = 0x00bc31ff   esp = 0x0910fdb4   ebp = 0x0910fdcc
    Found by: previous frame's frame pointer
 3  nspr4.dll!_PR_WaitCondVar [prucv.c : 204 + 0x16]
    eip = 0x00bba871   esp = 0x0910fdd4   ebp = 0x0910fde8
    Found by: call frame info
 4  nspr4.dll!PR_Wait [prmon.c : 184 + 0x1c]
    eip = 0x00bba0e3   esp = 0x0910fdf0   ebp = 0x0910fe0c
    Found by: call frame info
 5  xul.dll!nsAutoMonitor::Wait(unsigned int) [nsAutoLock.h : 346 + 0x10]
    eip = 0x1071b138   esp = 0x0910fe14   ebp = 0x0910fe20
    Found by: call frame info
 6  xul.dll!nsThreadPool::Run() [nsThreadPool.cpp : 212 + 0xb]
    eip = 0x114a8ad6   esp = 0x0910fe28   ebp = 0x0910feac
    Found by: call frame info
 7  xul.dll!nsThread::ProcessNextEvent(int,int *) [nsThread.cpp : 609 + 0x18]
    eip = 0x114ab08a   esp = 0x0910feb4   ebp = 0x0910fee8
    Found by: call frame info
 8  xul.dll!NS_ProcessNextEvent_P(nsIThread *,int) [nsThreadUtils.cpp : 250 + 0x15]
    eip = 0x10575b43   esp = 0x0910fef0   ebp = 0x0910ff04
    Found by: call frame info
 9  xul.dll!nsThread::ThreadFunc(void *) [nsThread.cpp : 277 + 0xa]
    eip = 0x114aa10e   esp = 0x0910ff0c   ebp = 0x0910ff4c
    Found by: call frame info
10  nspr4.dll!_PR_NativeRunThread [pruthr.c : 426 + 0xe]
    eip = 0x00bbc87b   esp = 0x0910ff54   ebp = 0x0910ff5c
    Found by: call frame info
11  nspr4.dll!pr_root [w95thred.c : 122 + 0xe]
    eip = 0x00bc0f09   esp = 0x0910ff64   ebp = 0x0910ff6c
    Found by: call frame info
12  msvcr80d.dll + 0x48d0
    eip = 0x005348d1   esp = 0x0910ff74   ebp = 0x0910ffa8
    Found by: call frame info
13  msvcr80d.dll + 0x4876
    eip = 0x00534877   esp = 0x0910ffb0   ebp = 0x0910ffb4
    Found by: previous frame's frame pointer
14  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x0910ffbc   ebp = 0x0910ffec
    Found by: previous frame's frame pointer

Thread 24
 0  ntdll.dll + 0xe514
    eip = 0x7c90e514   esp = 0x093ffd74   ebp = 0x093ffdd8   ebx = 0x087d6460
    esi = 0x00000404   edi = 0x00000000   eax = 0xcdcdcdcd   ecx = 0x00000428
    edx = 0x00000000   efl = 0x00000246
    Found by: given as instruction pointer in context
 1  kernel32.dll + 0x2541
    eip = 0x7c802542   esp = 0x093ffde0   ebp = 0x093ffdec
    Found by: previous frame's frame pointer
 2  nspr4.dll!_PR_MD_WAIT_CV [w95cv.c : 280 + 0x13]
    eip = 0x00bc31ff   esp = 0x093ffdf4   ebp = 0x093ffe0c
    Found by: previous frame's frame pointer
 3  nspr4.dll!_PR_WaitCondVar [prucv.c : 204 + 0x16]
    eip = 0x00bba871   esp = 0x093ffe14   ebp = 0x093ffe28
    Found by: call frame info
 4  nspr4.dll!PR_Wait [prmon.c : 184 + 0x1c]
    eip = 0x00bba0e3   esp = 0x093ffe30   ebp = 0x093ffe4c
    Found by: call frame info
 5  xul.dll!nsAutoMonitor::Wait(unsigned int) [nsAutoLock.h : 346 + 0x10]
    eip = 0x1071b138   esp = 0x093ffe54   ebp = 0x093ffe60
    Found by: call frame info
 6  xul.dll!nsEventQueue::GetEvent(int,nsIRunnable * *) [nsEventQueue.cpp : 85 + 0x9]
    eip = 0x114a99ab   esp = 0x093ffe68   ebp = 0x093ffe94
    Found by: call frame info
 7  xul.dll!nsThread::nsChainedEventQueue::GetEvent(int,nsIRunnable * *) [nsThread.h : 112 + 0x12]
    eip = 0x114aa27a   esp = 0x093ffe9c   ebp = 0x093ffea8
    Found by: call frame info
 8  xul.dll!nsThread::ProcessNextEvent(int,int *) [nsThread.cpp : 592 + 0x48]
    eip = 0x114ab01f   esp = 0x093ffeb0   ebp = 0x093ffee8
    Found by: call frame info
 9  xul.dll!NS_ProcessNextEvent_P(nsIThread *,int) [nsThreadUtils.cpp : 250 + 0x15]
    eip = 0x10575b43   esp = 0x093ffef0   ebp = 0x093fff04
    Found by: call frame info
10  xul.dll!nsThread::ThreadFunc(void *) [nsThread.cpp : 277 + 0xa]
    eip = 0x114aa10e   esp = 0x093fff0c   ebp = 0x093fff4c
    Found by: call frame info
11  nspr4.dll!_PR_NativeRunThread [pruthr.c : 426 + 0xe]
    eip = 0x00bbc87b   esp = 0x093fff54   ebp = 0x093fff5c
    Found by: call frame info
12  nspr4.dll!pr_root [w95thred.c : 122 + 0xe]
    eip = 0x00bc0f09   esp = 0x093fff64   ebp = 0x093fff6c
    Found by: call frame info
13  msvcr80d.dll + 0x48d0
    eip = 0x005348d1   esp = 0x093fff74   ebp = 0x093fffa8
    Found by: call frame info
14  msvcr80d.dll + 0x4876
    eip = 0x00534877   esp = 0x093fffb0   ebp = 0x093fffb4
    Found by: previous frame's frame pointer
15  kernel32.dll + 0xb728
    eip = 0x7c80b729   esp = 0x093fffbc   ebp = 0x093fffec
    Found by: previous frame's frame pointer

Loaded modules:
0x00290000 - 0x003f4fff  mozsqlite3.dll  3.7.1.0  (main)
0x00400000 - 0x00519fff  firefox.exe  2.0.0.3952
0x00530000 - 0x00650fff  msvcr80d.dll  8.0.50727.4053
0x00660000 - 0x00b87fff  mozjs.dll  ???
0x00b90000 - 0x00bdefff  nspr4.dll  4.8.7.0
0x00bf0000 - 0x00cedfff  msvcp80d.dll  8.0.50727.4053
0x00cf0000 - 0x00d2afff  smime3.dll  3.12.8.0
0x00d40000 - 0x00eb9fff  nss3.dll  3.12.8.0
0x00ed0000 - 0x00efbfff  nssutil3.dll  3.12.8.0
0x00f10000 - 0x00f1bfff  plc4.dll  4.8.7.0
0x00f30000 - 0x00f3afff  plds4.dll  4.8.7.0
0x00f50000 - 0x00fadfff  ssl3.dll  3.12.8.0
0x00fc0000 - 0x00fcafff  mozalloc.dll  2.0.0.3952
0x00fe0000 - 0x00feafff  xpcom.dll  2.0.0.3952
0x01e00000 - 0x01e08fff  normaliz.dll  6.0.5441.0
0x05d00000 - 0x05e0efff  browsercomps.dll  2.0.0.3952
0x05f40000 - 0x05f8afff  softokn3.dll  3.12.8.0
0x05fa0000 - 0x05fd7fff  nssdbm3.dll  3.12.8.0
0x06810000 - 0x06ad4fff  xpsp2res.dll  5.1.2600.5512
0x07560000 - 0x075d6fff  freebl3.dll  3.12.8.0
0x075e0000 - 0x07669fff  nssckbi.dll  1.80.0.0
0x10000000 - 0x1305bfff  xul.dll  2.0.0.3952
0x3d930000 - 0x3da00fff  wininet.dll  7.0.6000.17091
0x3dfd0000 - 0x3e014fff  iertutil.dll  7.0.6000.17091
0x478c0000 - 0x478c9fff  dot3api.dll  5.1.2600.5512
0x4fdd0000 - 0x4ff75fff  d3d9.dll  5.3.2600.5512
0x59a60000 - 0x59b00fff  dbghelp.dll  5.1.2600.5512
0x5ad70000 - 0x5ada7fff  uxtheme.dll  6.0.2900.5512
0x5b860000 - 0x5b8b4fff  netapi32.dll  5.1.2600.5694
0x5dac0000 - 0x5dac7fff  rdpsnd.dll  5.1.2600.5512
0x5dca0000 - 0x5dcc7fff  onex.dll  5.1.2600.5512
0x5dcd0000 - 0x5dcddfff  eappprxy.dll  5.1.2600.5512
0x606b0000 - 0x607bcfff  esent.dll  5.1.2600.5512
0x662b0000 - 0x66307fff  hnetcfg.dll  5.1.2600.5512
0x693f0000 - 0x693f8fff  feclient.dll  5.1.2600.5512
0x6d990000 - 0x6d995fff  d3d8thk.dll  5.3.2600.5512
0x71a50000 - 0x71a8efff  mswsock.dll  5.1.2600.5625
0x71a90000 - 0x71a97fff  wshtcpip.dll  5.1.2600.5512
0x71aa0000 - 0x71aa7fff  ws2help.dll  5.1.2600.5512
0x71ab0000 - 0x71ac6fff  ws2_32.dll  5.1.2600.5512
0x71ad0000 - 0x71ad8fff  wsock32.dll  5.1.2600.5512
0x71b20000 - 0x71b31fff  mpr.dll  5.1.2600.5512
0x71bf0000 - 0x71c02fff  samlib.dll  5.1.2600.5512
0x726c0000 - 0x726d5fff  qutil.dll  5.1.2600.5512
0x72810000 - 0x7281afff  eapolqec.dll  5.1.2600.5512
0x73000000 - 0x73025fff  winspool.drv  5.1.2600.5512
0x73030000 - 0x7303ffff  wzcsapi.dll  5.1.2600.5512
0x736d0000 - 0x736d5fff  dot3dlg.dll  5.1.2600.5512
0x73b30000 - 0x73b44fff  mscms.dll  5.1.2600.5627
0x73ce0000 - 0x73d00fff  t2embed.dll  5.1.2600.6031
0x73dc0000 - 0x73dc2fff  lz32.dll  5.1.2600.0
0x745b0000 - 0x745d1fff  eappcfg.dll  5.1.2600.5512
0x74d90000 - 0x74dfafff  usp10.dll  1.420.2600.5969
0x76080000 - 0x760e4fff  msvcp60.dll  6.2.3104.0
0x76360000 - 0x7636ffff  winsta.dll  5.1.2600.5512
0x76380000 - 0x76384fff  msimg32.dll  5.1.2600.5512
0x76390000 - 0x763acfff  imm32.dll  5.1.2600.5512
0x763b0000 - 0x763f8fff  comdlg32.dll  6.0.2900.5512
0x76400000 - 0x765a4fff  netshell.dll  5.1.2600.5512
0x769c0000 - 0x76a73fff  userenv.dll  5.1.2600.5512
0x76b20000 - 0x76b30fff  atl.dll  3.5.2284.2
0x76b40000 - 0x76b6cfff  winmm.dll  5.1.2600.5512
0x76bf0000 - 0x76bfafff  psapi.dll  5.1.2600.5512
0x76c00000 - 0x76c2dfff  credui.dll  5.1.2600.5512
0x76d30000 - 0x76d33fff  wmi.dll  5.1.2600.5512
0x76d40000 - 0x76d57fff  mprapi.dll  5.1.2600.5512
0x76d60000 - 0x76d78fff  iphlpapi.dll  5.1.2600.5512
0x76e10000 - 0x76e34fff  adsldpc.dll  5.1.2600.5512
0x76e80000 - 0x76e8dfff  rtutils.dll  5.1.2600.5512
0x76e90000 - 0x76ea1fff  rasman.dll  5.1.2600.5512
0x76eb0000 - 0x76edefff  tapi32.dll  5.1.2600.5512
0x76ee0000 - 0x76f1bfff  rasapi32.dll  5.1.2600.5512
0x76f20000 - 0x76f46fff  dnsapi.dll  5.1.2600.5625
0x76f50000 - 0x76f57fff  wtsapi32.dll  5.1.2600.5512
0x76f60000 - 0x76f8bfff  wldap32.dll  5.1.2600.5512
0x76fb0000 - 0x76fb7fff  winrnr.dll  5.1.2600.5512
0x76fc0000 - 0x76fc5fff  rasadhlp.dll  5.1.2600.5512
0x76fd0000 - 0x7704efff  clbcatq.dll  2001.12.4414.700
0x77050000 - 0x77114fff  comres.dll  2001.12.4414.700
0x77120000 - 0x771aafff  oleaut32.dll  5.1.2600.5512
0x773d0000 - 0x774d2fff  comctl32.dll  6.0.2900.6028
0x774e0000 - 0x7761dfff  ole32.dll  5.1.2600.6010
0x77690000 - 0x776b0fff  ntmarta.dll  5.1.2600.5512
0x77920000 - 0x77a12fff  setupapi.dll  5.1.2600.5512
0x77a80000 - 0x77b14fff  crypt32.dll  5.131.2600.5512
0x77b20000 - 0x77b31fff  msasn1.dll  5.1.2600.5875
0x77c00000 - 0x77c07fff  version.dll  5.1.2600.5512
0x77c10000 - 0x77c67fff  msvcrt.dll  7.0.2600.5512
0x77cc0000 - 0x77cf1fff  activeds.dll  5.1.2600.5512
0x77d00000 - 0x77d32fff  netman.dll  5.1.2600.5512
0x77dd0000 - 0x77e6afff  advapi32.dll  5.1.2600.5755
0x77e70000 - 0x77f02fff  rpcrt4.dll  5.1.2600.6022
0x77f10000 - 0x77f58fff  gdi32.dll  5.1.2600.5698
0x77f60000 - 0x77fd5fff  shlwapi.dll  6.0.2900.5912
0x77fe0000 - 0x77ff0fff  secur32.dll  5.1.2600.5834
0x7c800000 - 0x7c8f5fff  kernel32.dll  5.1.2600.5781
0x7c900000 - 0x7c9b1fff  ntdll.dll  5.1.2600.5755
0x7c9c0000 - 0x7d1d6fff  shell32.dll  6.0.2900.6018
0x7d4b0000 - 0x7d4d1fff  dhcpcsvc.dll  5.1.2600.5512
0x7db10000 - 0x7db9bfff  wzcsvc.dll  5.1.2600.5512
0x7e410000 - 0x7e4a0fff  user32.dll  5.1.2600.5512

 EXIT STATUS: NORMAL (10.984000 seconds)
""",
"""
Operating system: Linux
                  0.0.0 Linux 2.6.18-194.17.4.el5 #1 SMP Mon Oct 25 15:51:07 EDT 2010 i686
CPU: x86
     GenuineIntel family 6 model 23 stepping 6
     1 CPU

Crash reason:  SIGSEGV
Crash address: 0x92819388

Thread 0 (crashed)
 0  0x92819388
    eip = 0x92819388   esp = 0xbf8007b0   ebp = 0x00000000   ebx = 0x03855264
    esi = 0x00000000   edi = 0x024d8e0a   eax = 0x00000000   ecx = 0x00000010
    edx = 0x00050720   efl = 0x00010282
    Found by: given as instruction pointer in context
 1  libpthread-2.5.so + 0x9fff
    eip = 0x00410000   esp = 0xbf8007b4   ebp = 0x00000000
    Found by: stack scanning
 2  librt-2.5.so + 0x3f
    eip = 0x00280040   esp = 0xbf8007d4   ebp = 0x00000000
    Found by: stack scanning
 3  libpango-1.0.so.0.1400.9 + 0x3f73
    eip = 0x00296f74   esp = 0xbf8007e8   ebp = 0x00000000
    Found by: stack scanning
 4  librt-2.5.so + 0xf
    eip = 0x00280010   esp = 0xbf800804   ebp = 0x00000000
    Found by: stack scanning
 5  libssl3.so!getWrappingKey [ssl3con.c : 4487 + 0x2]
    eip = 0x00a607e8   esp = 0xbf800808   ebp = 0x00000000
    Found by: stack scanning
 6  libpango-1.0.so.0.1400.9 + 0x735f
    eip = 0x0029a360   esp = 0xbf800818   ebp = 0x00000000
    Found by: stack scanning
 7  libmozsqlite3.so!sqlite3BtreePutData [sqlite3.c : 52528 + 0xe]
    eip = 0x00890070   esp = 0xbf800820   ebp = 0x00000000
    Found by: stack scanning
 8  libX11.so.6.2.0 + 0xa3fff
    eip = 0x009f2000   esp = 0xbf800824   ebp = 0x00000000
    Found by: stack scanning
 9  libplc4.so!encode [base64.c : 126 + 0x3]
    eip = 0x00290028   esp = 0xbf80082c   ebp = 0x00000000
    Found by: stack scanning
10  libcairo.so.2.9.2 + 0x32748
    eip = 0x00304749   esp = 0xbf800830   ebp = 0x00000000
    Found by: stack scanning
11  libpthread-2.5.so + 0xa9c4
    eip = 0x004109c5   esp = 0xbf800840   ebp = 0x00000000
    Found by: stack scanning
12  libnspr4.so!PR_GetCurrentThread [ptthread.c : 614 + 0xd]
    eip = 0x00147266   esp = 0xbf800850   ebp = 0x00000000
    Found by: stack scanning
13  libxul.so!NS_LogRelease_P [nsTraceRefcntImpl.cpp : 1051 + 0x4]
    eip = 0x02503800   esp = 0xbf800860   ebp = 0x00000000
    Found by: stack scanning
14  libc-2.5.so + 0x68ee5
    eip = 0x03cd6ee6   esp = 0xbf80086c   ebp = 0x00000000
    Found by: stack scanning
15  libxul.so!AssertActivityIsLegal [nsTraceRefcntImpl.cpp : 167 + 0x18]
    eip = 0x0250202b   esp = 0xbf8008a0   ebp = 0x00000000
    Found by: stack scanning
16  libc-2.5.so + 0x126de1
    eip = 0x03d94de2   esp = 0xbf8008a8   ebp = 0x00000000
    Found by: stack scanning
17  libpthread-2.5.so + 0xa9c4
    eip = 0x004109c5   esp = 0xbf8008b0   ebp = 0x00000000
    Found by: stack scanning
18  libnspr4.so!PR_GetCurrentThread [ptthread.c : 614 + 0xd]
    eip = 0x00147266   esp = 0xbf8008c0   ebp = 0x00000000
    Found by: stack scanning
19  libxul.so!NS_LogDtor_P [nsTraceRefcntImpl.cpp : 1151 + 0x4]
    eip = 0x02503bdc   esp = 0xbf8008d0   ebp = 0x00000000
    Found by: stack scanning
20  libc-2.5.so + 0x68ee5
    eip = 0x03cd6ee6   esp = 0xbf8008dc   ebp = 0x00000000
    Found by: stack scanning
21  libpthread-2.5.so + 0xa9c4
    eip = 0x004109c5   esp = 0xbf800910   ebp = 0x00000000
    Found by: stack scanning
22  libnspr4.so!PR_GetCurrentThread [ptthread.c : 614 + 0xd]
    eip = 0x00147266   esp = 0xbf800920   ebp = 0x00000000
    Found by: stack scanning
23  libxul.so!nsCharPtrHashKey::HashKey [nsHashKeys.h : 361 + 0xa]
    eip = 0x01e93b88   esp = 0xbf800930   ebp = 0x00000000
    Found by: stack scanning
24  libnspr4.so!PR_GetThreadPrivate [prtpd.c : 232 + 0x4]
    eip = 0x0012aa8b   esp = 0xbf800950   ebp = 0x00000000
    Found by: stack scanning
25  libxul.so!AssertActivityIsLegal [nsTraceRefcntImpl.cpp : 167 + 0x18]
    eip = 0x0250202b   esp = 0xbf800970   ebp = 0x00000000
    Found by: stack scanning
26  libxul.so!nsVoidArray::~nsVoidArray [nsVoidArray.cpp : 376 + 0xc]
    eip = 0x02478fbc   esp = 0xbf800980   ebp = 0x00000000
    Found by: stack scanning
27  libxul.so!NS_LogRelease_P [nsTraceRefcntImpl.cpp : 1051 + 0x4]
    eip = 0x02503800   esp = 0xbf8009a0   ebp = 0x00000000
    Found by: stack scanning
28  libpthread-2.5.so + 0xa9c4
    eip = 0x004109c5   esp = 0xbf8009b0   ebp = 0x00000000
    Found by: stack scanning
29  libnspr4.so!PR_GetCurrentThread [ptthread.c : 614 + 0xd]
    eip = 0x00147266   esp = 0xbf8009c0   ebp = 0x00000000
    Found by: stack scanning
30  libxul.so!nsObserverService::Release [nsObserverService.cpp : 76 + 0x75]
    eip = 0x0249fe80   esp = 0xbf8009f0   ebp = 0x00000000
    Found by: stack scanning
31  libxul.so!NS_IsMainThread_P [nsThreadUtils.h : 114 + 0xb]
    eip = 0x00eff47c   esp = 0xbf800a04   ebp = 0x00000000
    Found by: stack scanning
32  libxul.so!nsObserverService::NotifyObservers [nsObserverService.cpp : 185 + 0x17]
    eip = 0x024a0745   esp = 0xbf800a10   ebp = 0x00000000
    Found by: stack scanning
33  libxul.so!send_tree [trees.c : 784 + 0x141]
    eip = 0x02ba0136   esp = 0xbf800a3c   ebp = 0x00000000
    Found by: stack scanning

Thread 1
 0  linux-gate.so + 0x402
    eip = 0x00b76402   esp = 0xb7efd0c8   ebp = 0xb7efd128   ebx = 0x0000000f
    esi = 0xffffffff   edi = 0x00000000   eax = 0xfffffffc   ecx = 0x0947e270
    edx = 0x000003ff   efl = 0x00200212
    Found by: given as instruction pointer in context
 1  0x9471d2f
    eip = 0x09471d30   esp = 0xb7efd130   ebp = 0xb7efd158
    Found by: previous frame's frame pointer
 2  libxul.so!event_base_loop [event.c : 513 + 0x1b]
    eip = 0x02539fb6   esp = 0xb7efd160   ebp = 0xb7efd198
    Found by: previous frame's frame pointer
 3  libxul.so!base::MessagePumpLibevent::Run [message_pump_libevent.cc : 330 + 0x15]
    eip = 0x025ac825   esp = 0xb7efd1a0   ebp = 0xb7efd1f8   ebx = 0x03855264
    Found by: call frame info
 4  libxul.so!MessageLoop::RunInternal [message_loop.cc : 219 + 0x20]
    eip = 0x02556963   esp = 0xb7efd200   ebp = 0xb7efd228   ebx = 0x03855264
    esi = 0x00000000
    Found by: call frame info
 5  libxul.so!MessageLoop::RunHandler [message_loop.cc : 202 + 0xa]
    eip = 0x025568e3   esp = 0xb7efd230   ebp = 0xb7efd248   ebx = 0x03855264
    esi = 0x00000000
    Found by: call frame info
 6  libxul.so!MessageLoop::Run [message_loop.cc : 176 + 0xa]
    eip = 0x02556887   esp = 0xb7efd250   ebp = 0xb7efd278   ebx = 0x03855264
    esi = 0x00000000
    Found by: call frame info
 7  libxul.so!base::Thread::ThreadMain [thread.cc : 156 + 0xd]
    eip = 0x0257b843   esp = 0xb7efd280   ebp = 0xb7efd388   ebx = 0x03855264
    esi = 0x00000000
    Found by: call frame info
 8  libxul.so!ThreadFunc [platform_thread_posix.cc : 26 + 0x11]
    eip = 0x025acdaa   esp = 0xb7efd390   ebp = 0xb7efd3b8   ebx = 0x0041bff4
    esi = 0x00000000
    Found by: call frame info
 9  libpthread-2.5.so + 0x5831
    eip = 0x0040b832   esp = 0xb7efd3c0   ebp = 0xb7efd4a8   ebx = 0x0041bff4
    esi = 0x00000000
    Found by: call frame info
10  libc-2.5.so + 0xd1f6d
    eip = 0x03d3ff6e   esp = 0xb7efd4b0   ebp = 0x00000000
    Found by: previous frame's frame pointer

Thread 2
 0  linux-gate.so + 0x402
    eip = 0x00b76402   esp = 0xb71b9110   ebp = 0xb71b9168   ebx = 0x09483f98
    esi = 0xb71b9118   edi = 0x00000205   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x00000205   efl = 0x00200202
    Found by: given as instruction pointer in context
 1  0x10964eaf
    eip = 0x10964eb0   esp = 0xb71b9170   ebp = 0x4cd723e9
    Found by: previous frame's frame pointer
 2  libnspr4.so!PR_WaitCondVar [ptsynch.c : 419 + 0x1d]
    eip = 0x0013f445   esp = 0xb71b9190   ebp = 0x4cd723e9
    Found by: stack scanning
 3  libxul.so!TimerThread::Run [TimerThread.cpp : 375 + 0x14]
    eip = 0x024f8322   esp = 0xb71b91c0   ebp = 0x4cd723e9
    Found by: stack scanning
 4  libxul.so!nsCOMPtr<nsIRunnable>::assign_from_qi [nsCOMPtr.h : 1214 + 0x11]
    eip = 0x00eb71af   esp = 0xb71b91d0   ebp = 0x4cd723e9
    Found by: stack scanning

Thread 3
 0  linux-gate.so + 0x402
    eip = 0x00b76402   esp = 0xb5db72dc   ebp = 0xb5db7328   ebx = 0x09604950
    esi = 0x00000000   edi = 0x00000009   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x00000009   efl = 0x00200216
    Found by: given as instruction pointer in context
 1  libxul.so!js::GCHelperThread::threadLoop [jsgc.cpp : 1995 + 0x15]
    eip = 0x02756026   esp = 0xb5db7330   ebp = 0xb5db7358
    Found by: previous frame's frame pointer
 2  libxul.so!js::GCHelperThread::threadMain [jsgc.cpp : 1981 + 0x17]
    eip = 0x02755fda   esp = 0xb5db7360   ebp = 0xb5db7388   ebx = 0x0015b464
    Found by: call frame info
 3  libnspr4.so!_pt_root [ptthread.c : 187 + 0x10]
    eip = 0x00146783   esp = 0xb5db7390   ebp = 0xb5db73b8   ebx = 0x0015b464
    Found by: call frame info
 4  libpthread-2.5.so + 0x5831
    eip = 0x0040b832   esp = 0xb5db73c0   ebp = 0xb5db74a8   ebx = 0x0041bff4
    Found by: call frame info
 5  libc-2.5.so + 0xd1f6d
    eip = 0x03d3ff6e   esp = 0xb5db74b0   ebp = 0x00000000
    Found by: previous frame's frame pointer

Thread 4
 0  linux-gate.so + 0x402
    eip = 0x00b76402   esp = 0xb53b6290   ebp = 0xb53b62e8   ebx = 0x096054e0
    esi = 0xb53b6298   edi = 0x00000025   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x00000025   efl = 0x00200212
    Found by: given as instruction pointer in context
 1  0x2c78cfb7
    eip = 0x2c78cfb8   esp = 0xb53b62f0   ebp = 0x4cd723e9
    Found by: previous frame's frame pointer
 2  libc-2.5.so + 0x83245
    eip = 0x03cf1246   esp = 0xb53b62fc   ebp = 0x4cd723e9
    Found by: stack scanning
 3  libnspr4.so!PR_WaitCondVar [ptsynch.c : 419 + 0x1d]
    eip = 0x0013f445   esp = 0xb53b6310   ebp = 0x4cd723e9
    Found by: stack scanning
 4  libxul.so!XPCJSRuntime::WatchdogMain [xpcjsruntime.cpp : 861 + 0x17]
    eip = 0x01cf0e71   esp = 0xb53b6340   ebp = 0x4cd723e9
    Found by: stack scanning

Thread 5
 0  linux-gate.so + 0x402
    eip = 0x00b76402   esp = 0xb439f0e0   ebp = 0xb439f138   ebx = 0x09a99dd8
    esi = 0xb439f0e8   edi = 0x0000004d   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x0000004d   efl = 0x00200206
    Found by: given as instruction pointer in context
 1  libfreebl3.so + 0x4efc7
    eip = 0x084dafc8   esp = 0xb439f140   ebp = 0x4cd72421
    Found by: previous frame's frame pointer
 2  libnspr4.so!PR_WaitCondVar [ptsynch.c : 419 + 0x1d]
    eip = 0x0013f445   esp = 0xb439f160   ebp = 0x4cd72421
    Found by: stack scanning
 3  libxul.so!nsEventQueue::GetEvent [nsEventQueue.cpp : 99 + 0xa]
    eip = 0x024ecfd1   esp = 0xb439f170   ebp = 0x4cd72421
    Found by: stack scanning
 4  libnspr4.so!PR_Wait [ptsynch.c : 614 + 0x14]
    eip = 0x0013fc13   esp = 0xb439f190   ebp = 0x4cd72421
    Found by: stack scanning
 5  libxul.so!nsAutoMonitor::Wait [nsAutoLock.h : 346 + 0x14]
    eip = 0x00fbb761   esp = 0xb439f1c0   ebp = 0x4cd72421
    Found by: stack scanning
 6  libxul.so!nsThreadPool::Run [nsThreadPool.cpp : 212 + 0x11]
    eip = 0x024f3002   esp = 0xb439f1e0   ebp = 0x4cd72421
    Found by: stack scanning

Thread 6
 0  linux-gate.so + 0x402
    eip = 0x00b76402   esp = 0xb398c16c   ebp = 0xb398c1b8   ebx = 0x09c2bbd8
    esi = 0x00000000   edi = 0x0000003f   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x0000003f   efl = 0x00200206
    Found by: given as instruction pointer in context
 1  libnspr4.so!PR_Wait [ptsynch.c : 614 + 0x14]
    eip = 0x0013fc13   esp = 0xb398c1c0   ebp = 0xb398c1e8
    Found by: previous frame's frame pointer
 2  libxul.so!nsAutoMonitor::Wait [nsAutoLock.h : 346 + 0x14]
    eip = 0x00fbb761   esp = 0xb398c1f0   ebp = 0xb398c208   ebx = 0x03855264
    Found by: call frame info
 3  libxul.so!nsEventQueue::GetEvent [nsEventQueue.cpp : 85 + 0x12]
    eip = 0x024ecf25   esp = 0xb398c210   ebp = 0xb398c258   ebx = 0x03855264
    Found by: call frame info
 4  libxul.so!nsThread::nsChainedEventQueue::GetEvent [nsThread.h : 112 + 0x1b]
    eip = 0x024efc5a   esp = 0xb398c260   ebp = 0xb398c278   ebx = 0x03855264
    esi = 0xb398c2b8   edi = 0x01cc1d63
    Found by: call frame info
 5  libxul.so!nsThread::ProcessNextEvent [nsThread.cpp : 592 + 0x5b]
    eip = 0x024ef365   esp = 0xb398c280   ebp = 0xb398c2e8   ebx = 0x03855264
    esi = 0xb398c2b8   edi = 0x01cc1d63
    Found by: call frame info
 6  libxul.so!NS_ProcessNextEvent_P [nsThreadUtils.cpp : 250 + 0x1f]
    eip = 0x0247c5a5   esp = 0xb398c2f0   ebp = 0xb398c328   ebx = 0x03855264
    esi = 0x00000000   edi = 0xb398cb90
    Found by: call frame info
 7  libxul.so!nsThread::ThreadFunc [nsThread.cpp : 277 + 0x12]
    eip = 0x024ee3cd   esp = 0xb398c330   ebp = 0xb398c388   ebx = 0x03855264
    esi = 0x00000000   edi = 0xb398cb90
    Found by: call frame info
 8  libnspr4.so!_pt_root [ptthread.c : 187 + 0x10]
    eip = 0x00146783   esp = 0xb398c390   ebp = 0xb398c3b8   ebx = 0x0015b464
    esi = 0x00000000   edi = 0xb398cb90
    Found by: call frame info
 9  libpthread-2.5.so + 0x5831
    eip = 0x0040b832   esp = 0xb398c3c0   ebp = 0xb398c4a8   ebx = 0x0041bff4
    esi = 0x00000000   edi = 0xb398cb90
    Found by: call frame info
10  libc-2.5.so + 0xd1f6d
    eip = 0x03d3ff6e   esp = 0xb398c4b0   ebp = 0x00000000
    Found by: previous frame's frame pointer

Thread 7
 0  linux-gate.so + 0x402
    eip = 0x00b76402   esp = 0xb2f8abc8   ebp = 0xb2f8abf8   ebx = 0x0000001c
    esi = 0x0206c820   edi = 0x09c8fa48   eax = 0x00000000   ecx = 0x00000000
    edx = 0x00936590   efl = 0x00200246
    Found by: given as instruction pointer in context
 1  libmozsqlite3.so!unixSync [sqlite3.c : 25558 + 0x1b]
    eip = 0x00867b42   esp = 0xb2f8ac00   ebp = 0xb2f8ac38
    Found by: previous frame's frame pointer
 2  libmozsqlite3.so!sqlite3OsSync [sqlite3.c : 13413 + 0x16]
    eip = 0x0085e031   esp = 0xb2f8ac40   ebp = 0xb2f8ac58   ebx = 0x00936590
    Found by: call frame info
 3  libmozsqlite3.so!zeroJournalHdr [sqlite3.c : 35450 + 0x1e]
    eip = 0x0086f13b   esp = 0xb2f8ac60   ebp = 0xb2f8aca8   ebx = 0x00936590
    Found by: call frame info
 4  libmozsqlite3.so!pager_end_transaction [sqlite3.c : 36074 + 0x11]
    eip = 0x0087022c   esp = 0xb2f8acb0   ebp = 0xb2f8acd8   ebx = 0x00936590
    Found by: call frame info
 5  libmozsqlite3.so!sqlite3PagerCommitPhaseTwo [sqlite3.c : 39989 + 0x18]
    eip = 0x00876ca2   esp = 0xb2f8ace0   ebp = 0xb2f8ad18   ebx = 0x00936590
    Found by: call frame info
 6  libmozsqlite3.so!sqlite3BtreeCommitPhaseTwo [sqlite3.c : 47666 + 0xc]
    eip = 0x00883f20   esp = 0xb2f8ad20   ebp = 0xb2f8ad48   ebx = 0x00936590
    esi = 0x0206c820   edi = 0x09c8fa48
    Found by: call frame info
 7  libmozsqlite3.so!vdbeCommit [sqlite3.c : 56088 + 0xa]
    eip = 0x008980ec   esp = 0xb2f8ad50   ebp = 0xb2f8adc8   ebx = 0x00936590
    esi = 0x0206c820   edi = 0x09c8fa48
    Found by: call frame info
 8  libmozsqlite3.so!sqlite3VdbeHalt [sqlite3.c : 56500 + 0x11]
    eip = 0x00898b0f   esp = 0xb2f8add0   ebp = 0xb2f8ae08   ebx = 0x00936590
    esi = 0x0206c820   edi = 0x09c8fa48
    Found by: call frame info
 9  libmozsqlite3.so!sqlite3VdbeExec [sqlite3.c : 62182 + 0xa]
    eip = 0x008a3aae   esp = 0xb2f8ae10   ebp = 0xb2f8b008   ebx = 0x00936590
    esi = 0x0206c820   edi = 0x09c8fa48
    Found by: call frame info
10  libmozsqlite3.so!sqlite3Step [sqlite3.c : 57933 + 0xa]
    eip = 0x0089b9a3   esp = 0xb2f8b010   ebp = 0xb2f8b058   ebx = 0x00936590
    esi = 0x0206c820   edi = 0x09c8fa48
    Found by: call frame info
11  libmozsqlite3.so!sqlite3_step [sqlite3.c : 57997 + 0xa]
    eip = 0x0089bc18   esp = 0xb2f8b060   ebp = 0xb2f8b098   ebx = 0x00936590
    esi = 0x0206c820   edi = 0x09c8fa48
    Found by: call frame info
12  libmozsqlite3.so!sqlite3_exec [sqlite3.c : 83186 + 0xa]
    eip = 0x008cee6e   esp = 0xb2f8b0a0   ebp = 0xb2f8b0f8   ebx = 0x00936590
    esi = 0x0206c820   edi = 0x09c8fa48
    Found by: call frame info
13  libxul.so!mozilla::storage::Connection::ExecuteSimpleSQL [mozStorageConnection.cpp : 846 + 0x49]
    eip = 0x0206c88d   esp = 0xb2f8b100   ebp = 0xb2f8b138   ebx = 0x03855264
    esi = 0x0206c820   edi = 0x09c8fa48
    Found by: call frame info
14  libxul.so!mozilla::storage::Connection::CommitTransaction [mozStorageConnection.cpp : 944 + 0x35]
    eip = 0x0206cda5   esp = 0xb2f8b140   ebp = 0xb2f8b178   ebx = 0x03855264
    esi = 0x0206c820   edi = 0x09c8fa48
    Found by: call frame info
15  libxul.so!mozStorageTransaction::Commit [mozStorageHelper.h : 101 + 0x16]
    eip = 0x00f91fe8   esp = 0xb2f8b180   ebp = 0xb2f8b1a8   ebx = 0x03855264
    esi = 0x00000001   edi = 0x09c8fa48
    Found by: call frame info
16  libxul.so!mozilla::storage::AsyncExecuteStatements::notifyComplete [mozStorageAsyncStatementExecution.cpp : 434 + 0xd]
    eip = 0x0207cd8f   esp = 0xb2f8b1b0   ebp = 0xb2f8b208   ebx = 0x03855264
    esi = 0x00000001   edi = 0x09c8fa48
    Found by: call frame info
17  libxul.so!mozilla::storage::AsyncExecuteStatements::Run [mozStorageAsyncStatementExecution.cpp : 612 + 0xa]
    eip = 0x0207d8f1   esp = 0xb2f8b210   ebp = 0xb2f8b278   ebx = 0x03855264
    esi = 0x00000001   edi = 0x09c8fa48
    Found by: call frame info
18  libxul.so!nsThread::ProcessNextEvent [nsThread.cpp : 609 + 0x16]
    eip = 0x024ef3e5   esp = 0xb2f8b280   ebp = 0xb2f8b2e8   ebx = 0x03855264
    esi = 0xb2f8b2b8   edi = 0x01cc1d63
    Found by: call frame info
19  libxul.so!NS_ProcessNextEvent_P [nsThreadUtils.cpp : 250 + 0x1f]
    eip = 0x0247c5a5   esp = 0xb2f8b2f0   ebp = 0xb2f8b328   ebx = 0x03855264
    esi = 0x00000000   edi = 0xb2f8bb90
    Found by: call frame info
20  libxul.so!nsThread::ThreadFunc [nsThread.cpp : 277 + 0x12]
    eip = 0x024ee3cd   esp = 0xb2f8b330   ebp = 0xb2f8b388   ebx = 0x03855264
    esi = 0x00000000   edi = 0xb2f8bb90
    Found by: call frame info
21  libnspr4.so!_pt_root [ptthread.c : 187 + 0x10]
    eip = 0x00146783   esp = 0xb2f8b390   ebp = 0xb2f8b3b8   ebx = 0x0015b464
    esi = 0x00000000   edi = 0xb2f8bb90
    Found by: call frame info
22  libpthread-2.5.so + 0x5831
    eip = 0x0040b832   esp = 0xb2f8b3c0   ebp = 0xb2f8b4a8   ebx = 0x0041bff4
    esi = 0x00000000   edi = 0xb2f8bb90
    Found by: call frame info
23  libc-2.5.so + 0xd1f6d
    eip = 0x03d3ff6e   esp = 0xb2f8b4b0   ebp = 0x00000000
    Found by: previous frame's frame pointer

Thread 8
 0  linux-gate.so + 0x402
    eip = 0x00b76402   esp = 0xb195716c   ebp = 0xb19571b8   ebx = 0x0a12a208
    esi = 0x00000000   edi = 0x00000785   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x00000785   efl = 0x00000202
    Found by: given as instruction pointer in context
 1  libnspr4.so!PR_Wait [ptsynch.c : 614 + 0x14]
    eip = 0x0013fc13   esp = 0xb19571c0   ebp = 0xb19571e8
    Found by: previous frame's frame pointer
 2  libxul.so!nsAutoMonitor::Wait [nsAutoLock.h : 346 + 0x14]
    eip = 0x00fbb761   esp = 0xb19571f0   ebp = 0xb1957208   ebx = 0x03855264
    Found by: call frame info
 3  libxul.so!nsEventQueue::GetEvent [nsEventQueue.cpp : 85 + 0x12]
    eip = 0x024ecf25   esp = 0xb1957210   ebp = 0xb1957258   ebx = 0x03855264
    Found by: call frame info
 4  libxul.so!nsThread::nsChainedEventQueue::GetEvent [nsThread.h : 112 + 0x1b]
    eip = 0x024efc5a   esp = 0xb1957260   ebp = 0xb1957278   ebx = 0x03855264
    esi = 0xb19572b8   edi = 0x01cc1d63
    Found by: call frame info
 5  libxul.so!nsThread::ProcessNextEvent [nsThread.cpp : 592 + 0x5b]
    eip = 0x024ef365   esp = 0xb1957280   ebp = 0xb19572e8   ebx = 0x03855264
    esi = 0xb19572b8   edi = 0x01cc1d63
    Found by: call frame info
 6  libxul.so!NS_ProcessNextEvent_P [nsThreadUtils.cpp : 250 + 0x1f]
    eip = 0x0247c5a5   esp = 0xb19572f0   ebp = 0xb1957328   ebx = 0x03855264
    esi = 0x00000000   edi = 0xb1957b90
    Found by: call frame info
 7  libxul.so!nsThread::ThreadFunc [nsThread.cpp : 277 + 0x12]
    eip = 0x024ee3cd   esp = 0xb1957330   ebp = 0xb1957388   ebx = 0x03855264
    esi = 0x00000000   edi = 0xb1957b90
    Found by: call frame info
 8  libnspr4.so!_pt_root [ptthread.c : 187 + 0x10]
    eip = 0x00146783   esp = 0xb1957390   ebp = 0xb19573b8   ebx = 0x0015b464
    esi = 0x00000000   edi = 0xb1957b90
    Found by: call frame info
 9  libpthread-2.5.so + 0x5831
    eip = 0x0040b832   esp = 0xb19573c0   ebp = 0xb19574a8   ebx = 0x0041bff4
    esi = 0x00000000   edi = 0xb1957b90
    Found by: call frame info
10  libc-2.5.so + 0xd1f6d
    eip = 0x03d3ff6e   esp = 0xb19574b0   ebp = 0x00000000
    Found by: previous frame's frame pointer

Thread 9
 0  linux-gate.so + 0x402
    eip = 0x00b76402   esp = 0xaf15316c   ebp = 0xaf1531b8   ebx = 0x0a255478
    esi = 0x00000000   edi = 0x0000002b   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x0000002b   efl = 0x00000206
    Found by: given as instruction pointer in context
 1  libnspr4.so!PR_Wait [ptsynch.c : 614 + 0x14]
    eip = 0x0013fc13   esp = 0xaf1531c0   ebp = 0xaf1531e8
    Found by: previous frame's frame pointer
 2  libxul.so!nsAutoMonitor::Wait [nsAutoLock.h : 346 + 0x14]
    eip = 0x00fbb761   esp = 0xaf1531f0   ebp = 0xaf153208   ebx = 0x03855264
    Found by: call frame info
 3  libxul.so!nsEventQueue::GetEvent [nsEventQueue.cpp : 85 + 0x12]
    eip = 0x024ecf25   esp = 0xaf153210   ebp = 0xaf153258   ebx = 0x03855264
    Found by: call frame info
 4  libxul.so!nsThread::nsChainedEventQueue::GetEvent [nsThread.h : 112 + 0x1b]
    eip = 0x024efc5a   esp = 0xaf153260   ebp = 0xaf153278   ebx = 0x03855264
    esi = 0xaf1532b8   edi = 0x01cc1d63
    Found by: call frame info
 5  libxul.so!nsThread::ProcessNextEvent [nsThread.cpp : 592 + 0x5b]
    eip = 0x024ef365   esp = 0xaf153280   ebp = 0xaf1532e8   ebx = 0x03855264
    esi = 0xaf1532b8   edi = 0x01cc1d63
    Found by: call frame info
 6  libxul.so!NS_ProcessNextEvent_P [nsThreadUtils.cpp : 250 + 0x1f]
    eip = 0x0247c5a5   esp = 0xaf1532f0   ebp = 0xaf153328   ebx = 0x03855264
    esi = 0x00000000   edi = 0xaf153b90
    Found by: call frame info
 7  libxul.so!nsThread::ThreadFunc [nsThread.cpp : 277 + 0x12]
    eip = 0x024ee3cd   esp = 0xaf153330   ebp = 0xaf153388   ebx = 0x03855264
    esi = 0x00000000   edi = 0xaf153b90
    Found by: call frame info
 8  libnspr4.so!_pt_root [ptthread.c : 187 + 0x10]
    eip = 0x00146783   esp = 0xaf153390   ebp = 0xaf1533b8   ebx = 0x0015b464
    esi = 0x00000000   edi = 0xaf153b90
    Found by: call frame info
 9  libpthread-2.5.so + 0x5831
    eip = 0x0040b832   esp = 0xaf1533c0   ebp = 0xaf1534a8   ebx = 0x0041bff4
    esi = 0x00000000   edi = 0xaf153b90
    Found by: call frame info
10  libc-2.5.so + 0xd1f6d
    eip = 0x03d3ff6e   esp = 0xaf1534b0   ebp = 0x00000000
    Found by: previous frame's frame pointer

Thread 10
 0  linux-gate.so + 0x402
    eip = 0x00b76402   esp = 0xacfcc344   ebp = 0xacfcc358   ebx = 0xacfcc37c
    esi = 0x00000000   edi = 0x03dc2ff4   eax = 0xfffffffc   ecx = 0x00000002
    edx = 0xffffffff   efl = 0x00200246
    Found by: given as instruction pointer in context
 1  libxul.so!google_breakpad::CrashGenerationServer::Run [crash_generation_server.cc : 278 + 0x1a]
    eip = 0x00ec8144   esp = 0xacfcc360   ebp = 0xacfcc398
    Found by: previous frame's frame pointer
 2  libxul.so!google_breakpad::CrashGenerationServer::ThreadMain [crash_generation_server.cc : 462 + 0xa]
    eip = 0x00ec8895   esp = 0xacfcc3a0   ebp = 0xacfcc3b8   ebx = 0x0041bff4
    Found by: call frame info
 3  libpthread-2.5.so + 0x5831
    eip = 0x0040b832   esp = 0xacfcc3c0   ebp = 0xacfcc4a8   ebx = 0x0041bff4
    Found by: call frame info
 4  libc-2.5.so + 0xd1f6d
    eip = 0x03d3ff6e   esp = 0xacfcc4b0   ebp = 0x00000000
    Found by: previous frame's frame pointer

Loaded modules:
0x00110000 - 0x00111fff  libmozalloc.so  ???  (main)
0x00113000 - 0x00115fff  libplds4.so  ???
0x00117000 - 0x0015afff  libnspr4.so  ???
0x0015e000 - 0x00177fff  libatk-1.0.so.0.1212.0  ???
0x0017a000 - 0x00203fff  libgdk-x11-2.0.so.0.1000.4  ???
0x00207000 - 0x0021cfff  libgdk_pixbuf-2.0.so.0.1000.4  ???
0x0021e000 - 0x00225fff  libpangocairo-1.0.so.0.1400.9  ???
0x00227000 - 0x00228fff  libgmodule-2.0.so.0.1200.3  ???
0x0022a000 - 0x00234fff  libgcc_s-4.1.2-20080825.so.1  ???
0x00236000 - 0x00252fff  libnssutil3.so  ???
0x00256000 - 0x00257fff  libXinerama.so.1.0.0  ???
0x0025a000 - 0x00274fff  ld-2.5.so  ???
0x00277000 - 0x0027efff  libXrender.so.1.3.0  ???
0x00280000 - 0x00286fff  librt-2.5.so  ???
0x00289000 - 0x0028cfff  libgthread-2.0.so.0.1200.3  ???
0x0028e000 - 0x00291fff  libplc4.so  ???
0x00293000 - 0x002cffff  libpango-1.0.so.0.1400.9  ???
0x002d2000 - 0x0033dfff  libcairo.so.2.9.2  ???
0x00340000 - 0x0037dfff  libgobject-2.0.so.0.1200.3  ???
0x0037f000 - 0x003acfff  libsmime3.so  ???
0x003b0000 - 0x003befff  libXext.so.6.4.0  ???
0x003c0000 - 0x003c6fff  libXi.so.6.0.0  ???
0x003c8000 - 0x003cafff  libXrandr.so.2.0.0  ???
0x003cc000 - 0x003cffff  libXfixes.so.3.1.0  ???
0x003d1000 - 0x003d2fff  libXau.so.6.0.0  ???
0x003d4000 - 0x003fafff  libm-2.5.so  ???
0x003ff000 - 0x00401fff  libdl-2.5.so  ???
0x00406000 - 0x0041afff  libpthread-2.5.so  ???
0x0041f000 - 0x007affff  libgtk-x11-2.0.so.0.1000.4  ???
0x007b7000 - 0x00853fff  libglib-2.0.so.0.1200.3  ???
0x00855000 - 0x00934fff  libmozsqlite3.so  ???
0x00938000 - 0x00940fff  libXcursor.so.1.0.2  ???
0x00942000 - 0x00946fff  libXdmcp.so.6.0.0  ???
0x0094a000 - 0x0094cfff  libxpcom.so  ???
0x0094e000 - 0x00a4cfff  libX11.so.6.2.0  ???
0x00a51000 - 0x00a99fff  libssl3.so  ???
0x00a9c000 - 0x00b18fff  libfreetype.so.6.3.10  ???
0x00b1c000 - 0x00b42fff  libfontconfig.so.1.1.0  ???
0x00b4b000 - 0x00b5cfff  libz.so.1.2.3  ???
0x00b5e000 - 0x00b60fff  libcap.so.1.10  ???
0x00b62000 - 0x00b69fff  libSM.so.6.0.0  ???
0x00b6b000 - 0x00b6bfff  ISO8859-1.so  ???
0x00b6c000 - 0x00b6dfff  ISO8859-1.so  ???
0x00b6e000 - 0x00b74fff  libpopt.so.0.0.0  ???
0x00b76000 - 0x00b76fff  linux-gate.so  ???
0x00b77000 - 0x03731fff  libxul.so  ???
0x03c6e000 - 0x03dc0fff  libc-2.5.so  ???
0x03dc7000 - 0x03f30fff  libnss3.so  ???
0x03f36000 - 0x03f62fff  libpangoft2-1.0.so.0.1400.9  ???
0x03f64000 - 0x03f82fff  libexpat.so.0.5.0  ???
0x03f85000 - 0x03f9bfff  libICE.so.6.3.0  ???
0x03f9f000 - 0x03fa8fff  libnss_files-2.5.so  ???
0x03fab000 - 0x03fbafff  libresolv-2.5.so  ???
0x03fbf000 - 0x03fd4fff  libselinux.so.1  ???
0x03fd7000 - 0x03fd8fff  UTF-16.so  ???
0x03fdb000 - 0x03fdefff  libnss_dns-2.5.so  ???
0x03fe1000 - 0x03ff1fff  libclearlooks.so  ???
0x03ff3000 - 0x03ff6fff  libpixbufloader-png.so  ???
0x03ff8000 - 0x03ff9fff  libXss.so.1.0.0  ???
0x04226000 - 0x04351fff  libxml2.so.2.6.26  ???
0x043e4000 - 0x043f7fff  libmozgnome.so  ???
0x045f6000 - 0x045f7fff  libkeyutils-1.2.so  ???
0x04762000 - 0x047b4fff  libbrowsercomps.so  ???
0x049c7000 - 0x049c8fff  libcom_err.so.2.1  ???
0x0537e000 - 0x0539efff  libjpeg.so.62.0.0  ???
0x053dc000 - 0x05418fff  libdbus-1.so.3.4.0  ???
0x0585c000 - 0x05880fff  libpng12.so.0.10.0  ???
0x058bb000 - 0x058f5fff  libsepol.so.1  ???
0x05999000 - 0x059acfff  libnkgnomevfs.so  ???
0x05d43000 - 0x05d44fff  pango-basic-fc.so  ???
0x06517000 - 0x06640fff  libcrypto.so.0.9.8e  ???
0x0665a000 - 0x066ecfff  libkrb5.so.3.3  ???
0x066f2000 - 0x0670efff  libdbus-glib-1.so.2.1.0  ???
0x06712000 - 0x0673efff  libgssapi_krb5.so.2.2  ???
0x06742000 - 0x06766fff  libk5crypto.so.3.1  ???
0x0676a000 - 0x06843fff  libasound.so.2.0.0  ???
0x0684b000 - 0x0688efff  libssl.so.0.9.8e  ???
0x06895000 - 0x068e2fff  libORBit-2.so.0.1.0  ???
0x068ef000 - 0x06916fff  libaudiofile.so.0.0.2  ???
0x0691c000 - 0x06975fff  libbonobo-2.so.0.0.0  ???
0x06982000 - 0x0698afff  libesd.so.0.2.36  ???
0x0698e000 - 0x06991fff  libORBitCosNaming-2.so.0.1.0  ???
0x06995000 - 0x069a8fff  libbonobo-activation.so.4.0.0  ???
0x069ad000 - 0x069c1fff  libgnome-2.so.0.1600.0  ???
0x069c5000 - 0x069d0fff  libgnome-keyring.so.0.0.1  ???
0x069d5000 - 0x06a07fff  libgconf-2.so.4.1.0  ???
0x06a0d000 - 0x06a0efff  libutil-2.5.so  ???
0x06a13000 - 0x06a72fff  libgnomevfs-2.so.0.1600.2  ???
0x06a78000 - 0x06a86fff  libavahi-client.so.3.2.1  ???
0x06a8a000 - 0x06a94fff  libavahi-common.so.3.4.3  ???
0x06a98000 - 0x06a99fff  libavahi-glib.so.1.0.1  ???
0x06a9d000 - 0x06ab2fff  libart_lgpl_2.so.2.3.17  ???
0x06ab6000 - 0x06b95fff  libstdc++.so.6.0.8  ???
0x06ba3000 - 0x06bcefff  libgnomecanvas-2.so.0.1400.0  ???
0x06bd2000 - 0x06c35fff  libbonoboui-2.so.0.0.0  ???
0x06c3b000 - 0x06ccafff  libgnomeui-2.so.0.1600.0  ???
0x06f15000 - 0x06f68fff  libXt.so.6.0.0  ???
0x07200000 - 0x07205fff  libnotify.so.1.1.0  ???
0x0776e000 - 0x0777afff  libdbusservice.so  ???
0x07d4c000 - 0x07d60fff  libnsl-2.5.so  ???
0x08048000 - 0x0804bfff  firefox-bin  ???
0x08381000 - 0x08388fff  libkrb5support.so.0.1  ???
0x0848c000 - 0x084e5fff  libfreebl3.so  ???
0xacfcd000 - 0xadaf8fff  libflashplayer.so  ???
0xb2359000 - 0xb2392fff  DejaVuLGCSansMono.ttf  ???
0xb2393000 - 0xb23fffff  DejaVuLGCSans.ttf  ???
0xb251a000 - 0xb253dfff  n021003l.pfb  ???
0xb253e000 - 0xb2556fff  n019004l.pfb  ???
0xb2557000 - 0xb258afff  DejaVuLGCSerif.ttf  ???
0xb398d000 - 0xb399efff  spider.jar  ???
0xb43a0000 - 0xb43fffff  SYSV00000000 (deleted)  ???
0xb450b000 - 0xb4523fff  n019003l.pfb  ???
0xb4524000 - 0xb452bfff  cookies.sqlite-shm  ???
0xb452c000 - 0xb4598fff  DejaVuLGCSans.ttf  ???
0xb4599000 - 0xb459afff  87f5e051180a7a75f16eb6fe7dbd3749-x86.cache-2  ???
0xb459b000 - 0xb45a0fff  b79f3aaa7d385a141ab53ec885cc22a8-x86.cache-2  ???
0xb45a1000 - 0xb45a6fff  7ddba6133ef499da58de5e8c586d3b75-x86.cache-2  ???
0xb45a7000 - 0xb45a8fff  e3ead4b767b8819993a6fa3ae306afa9-x86.cache-2  ???
0xb45a9000 - 0xb45b0fff  e19de935dec46bbf3ed114ee4965548a-x86.cache-2  ???
0xb45b1000 - 0xb45b5fff  beeeeb3dfe132a8a0633a017c99ce0c0-x86.cache-2  ???
0xb71ba000 - 0xb74fcfff  omni.jar  ???
0xb7f12000 - 0xb7f18fff  gconv-modules.cache  ???

 EXIT STATUS: NORMAL (4.289101 seconds)
""",
"""
Operating system: Linux
                  0.0.0 Linux 2.6.18-194.11.3.el5 #1 SMP Mon Aug 30 16:23:24 EDT 2010 i686
CPU: x86
     GenuineIntel family 6 model 23 stepping 6
     1 CPU

Crash reason:  SIGABRT
Crash address: 0x26a9

Thread 0 (crashed)
 0  linux-gate.so + 0x402
    eip = 0x0058d402   esp = 0xbff45a3c   ebp = 0xbff45a48   ebx = 0x000026a9
    esi = 0x0ada5284   edi = 0x0054aff4   eax = 0x00000000   ecx = 0x000026a9
    edx = 0x00000006   efl = 0x00000206
    Found by: given as instruction pointer in context
 1  libxul.so!JS_Assert [jsutil.cpp : 83 + 0xb]
    eip = 0x0223e945   esp = 0xbff45a50   ebp = 0xbff45a78
    Found by: previous frame's frame pointer
 2  libxul.so!js::CompartmentChecker::fail [jscntxtinlines.h : 541 + 0x1f]
    eip = 0x020fac86   esp = 0xbff45a80   ebp = 0xbff45a98   ebx = 0x03267d44
    Found by: call frame info
 3  libxul.so!js::CompartmentChecker::check [jscntxtinlines.h : 549 + 0x14]
    eip = 0x020facdc   esp = 0xbff45aa0   ebp = 0xbff45ab8   ebx = 0x03267d44
    Found by: call frame info
 4  libxul.so!js::CompartmentChecker::check [jscntxtinlines.h : 557 + 0x19]
    eip = 0x020fad0a   esp = 0xbff45ac0   ebp = 0xbff45ad8   ebx = 0x03267d44
    Found by: call frame info
 5  libxul.so!js::assertSameCompartment<JSObject*> [jscntxtinlines.h : 624 + 0x11]
    eip = 0x020fe89e   esp = 0xbff45ae0   ebp = 0xbff45b08   ebx = 0x03267d44
    Found by: call frame info
 6  libxul.so!JS_GetPrototype [jsapi.cpp : 2886 + 0x11]
    eip = 0x020eb2a0   esp = 0xbff45b10   ebp = 0xbff45b38   ebx = 0x03267d44
    Found by: call frame info
 7  libxul.so!IsObjInProtoChain [nsDOMClassInfo.cpp : 9426 + 0x11]
    eip = 0x01234a21   esp = 0xbff45b40   ebp = 0xbff45b78   ebx = 0x03267d44
    esi = 0x0ada5284
    Found by: call frame info
 8  libxul.so!nsHTMLPluginObjElementSH::SetupProtoChain [nsDOMClassInfo.cpp : 9514 + 0x18]
    eip = 0x01234f78   esp = 0xbff45b80   ebp = 0xbff45bf8   ebx = 0x03267d44
    esi = 0x0ada5284
    Found by: call frame info
 9  libxul.so!nsHTMLPluginObjElementSH::PostCreate [nsDOMClassInfo.cpp : 9606 + 0x18]
    eip = 0x012351e1   esp = 0xbff45c00   ebp = 0xbff45c48   ebx = 0x03267d44
    esi = 0x0ada5284
    Found by: call frame info
10  libxul.so!FinishCreate [xpcwrappednative.cpp : 672 + 0x43]
    eip = 0x01720b1a   esp = 0xbff45c50   ebp = 0xbff45ce8   ebx = 0x03267d44
    esi = 0x0ada5284   edi = 0xb24538f8
    Found by: call frame info
11  libxul.so!XPCWrappedNative::GetNewOrUsed [xpcwrappednative.cpp : 602 + 0x38]
    eip = 0x01720855   esp = 0xbff45cf0   ebp = 0xbff45e98   ebx = 0x03267d44
    esi = 0xb241f268   edi = 0x0ada5370
    Found by: call frame info
12  libxul.so!XPCConvert::NativeInterface2JSObject [xpcconvert.cpp : 1290 + 0x57]
    eip = 0x016f71ef   esp = 0xbff45ea0   ebp = 0xbff45f78   ebx = 0x03267d44
    esi = 0x0aa4e97c   edi = 0xbff45ef0
    Found by: call frame info
13  libxul.so!NativeInterface2JSObject [nsXPConnect.cpp : 1191 + 0x4b]
    eip = 0x016d3356   esp = 0xbff45f80   ebp = 0xbff45fd8   ebx = 0x03267d44
    esi = 0x0aa4e97c   edi = 0x01230a3e
    Found by: call frame info
14  libxul.so!nsXPConnect::WrapNativeToJSVal [nsXPConnect.cpp : 1249 + 0x3e]
    eip = 0x016d3721   esp = 0xbff45fe0   ebp = 0xbff460c8   ebx = 0x03267d44
    esi = 0x0aa4e97c   edi = 0x01230a3e
    Found by: call frame info
15  libxul.so!nsContentUtils::WrapNative [nsContentUtils.cpp : 5541 + 0x4f]
    eip = 0x00e6ae4a   esp = 0xbff460d0   ebp = 0xbff46118   ebx = 0x03267d44
    esi = 0x0aa4e97c   edi = 0x01230a3e
    Found by: call frame info
16  libxul.so!nsContentUtils::WrapNative [nsContentUtils.h : 1616 + 0x3c]
    eip = 0x01238ba5   esp = 0xbff46120   ebp = 0xbff46148   ebx = 0x03267d44
    esi = 0x0aa4e97c   edi = 0x01230a3e
    Found by: call frame info
17  libxul.so!nsDOMClassInfo::WrapNative [nsDOMClassInfo.h : 175 + 0x34]
    eip = 0x01238ca0   esp = 0xbff46150   ebp = 0xbff46178   ebx = 0x03267d44
    esi = 0x0aa4e97c   edi = 0x01230a3e
    Found by: call frame info
18  libxul.so!nsArraySH::GetProperty [nsDOMClassInfo.cpp : 7987 + 0x3e]
    eip = 0x0122fea2   esp = 0xbff46180   ebp = 0xbff461e8   ebx = 0x03267d44
    esi = 0x0aa4e97c   edi = 0x01230a3e
    Found by: call frame info
19  libxul.so!nsNamedArraySH::GetProperty [nsDOMClassInfo.cpp : 8118 + 0x34]
    eip = 0x012305f7   esp = 0xbff461f0   ebp = 0xbff46248   ebx = 0x03267d44
    esi = 0x01731c2f   edi = 0xb45d8200
    Found by: call frame info
20  libxul.so!XPC_WN_Helper_GetProperty [xpcwrappednativejsops.cpp : 979 + 0x3b]
    eip = 0x0173255e   esp = 0xbff46250   ebp = 0xbff46288   ebx = 0x03267d44
    esi = 0x01731c2f   edi = 0xb45d8200
    Found by: call frame info
21  libxul.so!js::CallJSPropertyOp [jscntxtinlines.h : 728 + 0x1f]
    eip = 0x021aff12   esp = 0xbff46290   ebp = 0xbff462c8   ebx = 0x03267d44
    esi = 0x03162260   edi = 0xb45d8200
    Found by: call frame info
22  libxul.so!js::Shape::get [jsscopeinlines.h : 256 + 0x64]
    eip = 0x021b031b   esp = 0xbff462d0   ebp = 0xbff46308   ebx = 0x03267d44
    esi = 0x03162260   edi = 0xb45d8200
    Found by: call frame info
23  libxul.so!js_NativeGetInline [jsobj.cpp : 4863 + 0x26]
    eip = 0x021a8a84   esp = 0xbff46310   ebp = 0xbff46388   ebx = 0x03267d44
    esi = 0x03162260   edi = 0xb45d8200
    Found by: call frame info
24  libxul.so!js_GetPropertyHelperWithShapeInline [jsobj.cpp : 5037 + 0x2d]
    eip = 0x021a92fb   esp = 0xbff46390   ebp = 0xbff463f8   ebx = 0x03267d44
    esi = 0x03162260   edi = 0xb45d8200
    Found by: call frame info
25  libxul.so!js_GetPropertyHelperInline [jsobj.cpp : 5058 + 0x3b]
    eip = 0x021a93a0   esp = 0xbff46400   ebp = 0xbff46438   ebx = 0x03267d44
    esi = 0x03162260   edi = 0xb45d8200
    Found by: call frame info
26  libxul.so!js_GetProperty [jsobj.cpp : 5071 + 0x2e]
    eip = 0x021a9410   esp = 0xbff46440   ebp = 0xbff46468   ebx = 0x03267d44
    esi = 0x03162260   edi = 0xb45d8200
    Found by: call frame info
27  libxul.so!JSObject::getProperty [jsobj.h : 1075 + 0x34]
    eip = 0x020f7d94   esp = 0xbff46470   ebp = 0xbff464a8   ebx = 0x03267d44
    esi = 0x03162260   edi = 0xb45d8200
    Found by: call frame info
28  libxul.so!JSWrapper::get [jswrapper.cpp : 207 + 0x6b]
    eip = 0x0224035e   esp = 0xbff464b0   ebp = 0xbff464e8   ebx = 0x03267d44
    esi = 0x03162260   edi = 0xb45d8200
    Found by: call frame info
29  libxul.so!js::JSProxy::get [jsproxy.cpp : 760 + 0x39]
    eip = 0x021ebb8a   esp = 0xbff464f0   ebp = 0xbff46528   ebx = 0x03267d44
    esi = 0x03162260   edi = 0xb45d8200
    Found by: call frame info
30  libxul.so!js::proxy_GetProperty [jsproxy.cpp : 853 + 0x26]
    eip = 0x021ebf9f   esp = 0xbff46530   ebp = 0xbff46558   ebx = 0x03267d44
    esi = 0x03162260   edi = 0xb45d8200
    Found by: call frame info
31  libxul.so!JSObject::getProperty [jsobj.h : 1075 + 0x34]
    eip = 0x020f7d94   esp = 0xbff46560   ebp = 0xbff46598   ebx = 0x03267d44
    esi = 0x03162260   edi = 0xb45d8200
    Found by: call frame info
32  libxul.so!JSWrapper::get [jswrapper.cpp : 207 + 0x6b]
    eip = 0x0224035e   esp = 0xbff465a0   ebp = 0xbff465d8   ebx = 0x03267d44
    esi = 0x03162260   edi = 0xb45d8200
    Found by: call frame info
33  libxul.so!JSCrossCompartmentWrapper::get [jswrapper.cpp : 480 + 0xa4]
    eip = 0x022417c0   esp = 0xbff465e0   ebp = 0xbff46668   ebx = 0x03267d44
    esi = 0x03162260   edi = 0xb45d8200
    Found by: call frame info
34  libxul.so!xpc::CrossOriginWrapper::get [CrossOriginWrapper.cpp : 84 + 0x2d]
    eip = 0x017f5b6e   esp = 0xbff46670   ebp = 0xbff46698   ebx = 0x03267d44
    esi = 0x03162260   edi = 0xb45d8200
    Found by: call frame info
35  libxul.so!js::JSProxy::get [jsproxy.cpp : 760 + 0x39]
    eip = 0x021ebb8a   esp = 0xbff466a0   ebp = 0xbff466d8   ebx = 0x03267d44
    esi = 0x03162260   edi = 0xb45d8200
    Found by: call frame info
36  libxul.so!js::proxy_GetProperty [jsproxy.cpp : 853 + 0x26]
    eip = 0x021ebf9f   esp = 0xbff466e0   ebp = 0xbff46708   ebx = 0x03267d44
    esi = 0x03162260   edi = 0xb45d8200
    Found by: call frame info
37  libxul.so!JSObject::getProperty [jsobj.h : 1075 + 0x34]
    eip = 0x020f7d94   esp = 0xbff46710   ebp = 0xbff46748   ebx = 0x03267d44
    esi = 0x03162260   edi = 0xb45d8200
    Found by: call frame info
38  libxul.so!JSObject::getProperty [jsobj.h : 1079 + 0x26]
    eip = 0x020f7dc7   esp = 0xbff46750   ebp = 0xbff46778   ebx = 0x03267d44
    esi = 0x03162260   edi = 0xb45d8200
    Found by: call frame info
39  libxul.so!js::Interpret [jsinterp.cpp : 4513 + 0x28]
    eip = 0x0239534f   esp = 0xbff46780   ebp = 0xbff47578   ebx = 0x03267d44
    esi = 0x03162260   edi = 0xb45d8200
    Found by: call frame info
40  libxul.so!js::RunScript [jsinterp.cpp : 665 + 0x21]
    eip = 0x02184d4f   esp = 0xbff47580   ebp = 0xbff475a8   ebx = 0x03267d44
    esi = 0x00000000   edi = 0xbff47920
    Found by: call frame info
41  libxul.so!js::Invoke [jsinterp.cpp : 768 + 0x18]
    eip = 0x0218524c   esp = 0xbff475b0   ebp = 0xbff47628   ebx = 0x03267d44
    esi = 0x00000000   edi = 0xbff47920
    Found by: call frame info
42  libxul.so!js::ExternalInvoke [jsinterp.cpp : 881 + 0x19]
    eip = 0x02185853   esp = 0xbff47630   ebp = 0xbff47668   ebx = 0x03267d44
    esi = 0x00000008   edi = 0xbff47920
    Found by: call frame info
43  libxul.so!js::ExternalInvoke [jsinterp.h : 954 + 0x42]
    eip = 0x020d6832   esp = 0xbff47670   ebp = 0xbff476a8   ebx = 0x03267d44
    esi = 0xbff478a8   edi = 0xbff47920
    Found by: call frame info
44  libxul.so!JS_CallFunctionValue [jsapi.cpp : 4898 + 0x49]
    eip = 0x020f3552   esp = 0xbff476b0   ebp = 0xbff47708   ebx = 0x03267d44
    esi = 0xbff478a8   edi = 0xbff47920
    Found by: call frame info
45  libxul.so!nsXPCWrappedJSClass::CallMethod [xpcwrappedjsclass.cpp : 1694 + 0x4a]
    eip = 0x0171beb2   esp = 0xbff47710   ebp = 0xbff47b58   ebx = 0x03267d44
    esi = 0x00000001   edi = 0x01237e08
    Found by: call frame info
46  libxul.so!nsXPCWrappedJS::CallMethod [xpcwrappedjs.cpp : 577 + 0x33]
    eip = 0x017125c9   esp = 0xbff47b60   ebp = 0xbff47b98   ebx = 0x03267d44
    esi = 0x0171aa16   edi = 0x01712550
    Found by: call frame info
47  libxul.so!PrepareAndDispatch [xptcstubs_gcc_x86_unix.cpp : 95 + 0x3a]
    eip = 0x01f1f9db   esp = 0xbff47ba0   ebp = 0xbff47ca8   ebx = 0x03267d44
    esi = 0xbff47bdc   edi = 0x01712550
    Found by: call frame info
48  libxul.so!nsEventListenerManager::HandleEventSubType [nsEventListenerManager.cpp : 1112 + 0x18]
    eip = 0x00fafc2a   esp = 0xbff47cb0   ebp = 0xbff47df8   ebx = 0x03267d44
    esi = 0x0a96a8f8   edi = 0xbff47fd4
    Found by: call frame info
49  libxul.so!nsEventListenerManager::HandleEventInternal [nsEventListenerManager.cpp : 1208 + 0x3e]
    eip = 0x00fb000f   esp = 0xbff47e00   ebp = 0xbff47e88   ebx = 0x03267d44
    esi = 0x0a96a8f8   edi = 0xbff47fd4
    Found by: call frame info
50  libxul.so!nsEventListenerManager::HandleEvent [nsEventListenerManager.h : 146 + 0x3b]
    eip = 0x00fdc9c2   esp = 0xbff47e90   ebp = 0xbff47eb8   ebx = 0x03267d44
    esi = 0x0a5c6df8   edi = 0xbff47fd4
    Found by: call frame info
51  libxul.so!nsEventTargetChainItem::HandleEvent [nsEventDispatcher.cpp : 212 + 0x6f]
    eip = 0x00fdce84   esp = 0xbff47ec0   ebp = 0xbff47f08   ebx = 0x03267d44
    esi = 0x0a5c6df8   edi = 0xbff47fd4
    Found by: call frame info
52  libxul.so!nsEventTargetChainItem::HandleEventTargetChain [nsEventDispatcher.cpp : 311 + 0x4b]
    eip = 0x00fdaa64   esp = 0xbff47f10   ebp = 0xbff47f58   ebx = 0x03267d44
    esi = 0x0a473a00   edi = 0x009fb202
    Found by: call frame info
53  libxul.so!nsEventDispatcher::Dispatch [nsEventDispatcher.cpp : 628 + 0x35]
    eip = 0x00fdb80d   esp = 0xbff47f60   ebp = 0xbff48078   ebx = 0x03267d44
    esi = 0x0a473a00   edi = 0x009fb202
    Found by: call frame info
54  libxul.so!DocumentViewerImpl::LoadComplete [nsDocumentViewer.cpp : 1034 + 0x42]
    eip = 0x00b8c9a0   esp = 0xbff48080   ebp = 0xbff48118   ebx = 0x03267d44
    esi = 0x018155be   edi = 0x009fb202
    Found by: call frame info
55  libxul.so!nsDocShell::EndPageLoad [nsDocShell.cpp : 6021 + 0x22]
    eip = 0x01815720   esp = 0xbff48120   ebp = 0xbff483d8   ebx = 0x03267d44
    esi = 0x018155be   edi = 0x009fb202
    Found by: call frame info
56  libxul.so!nsDocShell::OnStateChange [nsDocShell.cpp : 5875 + 0x33]
    eip = 0x018150a1   esp = 0xbff483e0   ebp = 0xbff484a8   ebx = 0x03267d44
    esi = 0x018155be   edi = 0x0091b0cc
    Found by: call frame info
57  libxul.so!nsDocLoader::FireOnStateChange [nsDocLoader.cpp : 1334 + 0x32]
    eip = 0x01842935   esp = 0xbff484b0   ebp = 0xbff48558   ebx = 0x03267d44
    esi = 0x0181491c   edi = 0x0091b0cc
    Found by: call frame info
58  libxul.so!nsDocLoader::doStopDocumentLoad [nsDocLoader.cpp : 942 + 0x2a]
    eip = 0x018416f6   esp = 0xbff48560   ebp = 0xbff485e8   ebx = 0x03267d44
    esi = 0x00000000   edi = 0x0091b0cc
    Found by: call frame info
59  libxul.so!nsDocLoader::DocLoaderIsEmpty [nsDocLoader.cpp : 818 + 0x20]
    eip = 0x0184132e   esp = 0xbff485f0   ebp = 0xbff48658   ebx = 0x03267d44
    esi = 0x00000000   edi = 0x0091b0cc
    Found by: call frame info
60  libxul.so!nsDocLoader::OnStopRequest [nsDocLoader.cpp : 702 + 0x12]
    eip = 0x01840e9e   esp = 0xbff48660   ebp = 0xbff48738   ebx = 0x03267d44
    esi = 0x0a043188   edi = 0x0091b0cc
    Found by: call frame info
61  libxul.so!nsLoadGroup::RemoveRequest [nsLoadGroup.cpp : 680 + 0x2b]
    eip = 0x0091b381   esp = 0xbff48740   ebp = 0xbff487e8   ebx = 0x03267d44
    esi = 0x0a043188   edi = 0x0091b0cc
    Found by: call frame info
62  libxul.so!nsDocument::DoUnblockOnload [nsDocument.cpp : 7259 + 0x3c]
    eip = 0x00eb3a47   esp = 0xbff487f0   ebp = 0xbff48838   ebx = 0x03267d44
    esi = 0x0a043150   edi = 0x0091b0cc
    Found by: call frame info
63  libxul.so!nsDocument::UnblockOnload [nsDocument.cpp : 7201 + 0xa]
    eip = 0x00eb37f4   esp = 0xbff48840   ebp = 0xbff48868   ebx = 0x03267d44
    esi = 0xbff48938   edi = 0x00000000
    Found by: call frame info
64  libxul.so!nsLoadBlockingPLDOMEvent::~nsLoadBlockingPLDOMEvent [nsPLDOMEvent.cpp : 86 + 0x24]
    eip = 0x00fda52f   esp = 0xbff48870   ebp = 0xbff48898   ebx = 0x03267d44
    esi = 0xbff48938   edi = 0x00000000
    Found by: call frame info
65  libxul.so!nsRunnable::Release [nsThreadUtils.cpp : 55 + 0xa9]
    eip = 0x01e8f9f0   esp = 0xbff488a0   ebp = 0xbff488d8   ebx = 0x03267d44
    esi = 0xbff48938   edi = 0x00000000
    Found by: call frame info
66  libxul.so!nsCOMPtr<nsIRunnable>::~nsCOMPtr [nsCOMPtr.h : 533 + 0x15]
    eip = 0x008cda1c   esp = 0xbff488e0   ebp = 0xbff488f8   ebx = 0x03267d44
    esi = 0xbff48938   edi = 0x00000000
    Found by: call frame info
67  libxul.so!nsThread::ProcessNextEvent [nsThread.cpp : 614 + 0xa]
    eip = 0x01f02e2d   esp = 0xbff48900   ebp = 0xbff48968   ebx = 0x03267d44
    esi = 0xbff48938   edi = 0x00000000
    Found by: call frame info
68  libxul.so!NS_ProcessNextEvent_P [nsThreadUtils.cpp : 250 + 0x1f]
    eip = 0x01e8ff91   esp = 0xbff48970   ebp = 0xbff489a8   ebx = 0x03267d44
    esi = 0x00000001   edi = 0x09aa50c8
    Found by: call frame info
69  libxul.so!mozilla::ipc::MessagePump::Run [MessagePump.cpp : 110 + 0x15]
    eip = 0x01cfe82c   esp = 0xbff489b0   ebp = 0xbff489f8   ebx = 0x03267d44
    esi = 0x00000001   edi = 0x09aa50c8
    Found by: call frame info
70  libxul.so!MessageLoop::RunInternal [message_loop.cc : 219 + 0x20]
    eip = 0x01f6a34b   esp = 0xbff48a00   ebp = 0xbff48a28   ebx = 0x03267d44
    esi = 0x0a287db8   edi = 0x09aa50c8
    Found by: call frame info
71  libxul.so!MessageLoop::RunHandler [message_loop.cc : 202 + 0xa]
    eip = 0x01f6a2cb   esp = 0xbff48a30   ebp = 0xbff48a48   ebx = 0x03267d44
    esi = 0x0a287db8   edi = 0x09aa50c8
    Found by: call frame info
72  libxul.so!MessageLoop::Run [message_loop.cc : 176 + 0xa]
    eip = 0x01f6a26f   esp = 0xbff48a50   ebp = 0xbff48a78   ebx = 0x03267d44
    esi = 0x0a287db8   edi = 0x09aa50c8
    Found by: call frame info
73  libxul.so!nsBaseAppShell::Run [nsBaseAppShell.cpp : 181 + 0xc]
    eip = 0x01ba1cf4   esp = 0xbff48a80   ebp = 0xbff48ab8   ebx = 0x03267d44
    esi = 0x0a287db8   edi = 0x09aa50c8
    Found by: call frame info
74  libxul.so!nsAppStartup::Run [nsAppStartup.cpp : 191 + 0x19]
    eip = 0x018f2ff1   esp = 0xbff48ac0   ebp = 0xbff48af8   ebx = 0x03267d44
    esi = 0x0a287db8   edi = 0x09aa50c8
    Found by: call frame info
75  libxul.so!XRE_main [nsAppRunner.cpp : 3682 + 0x19]
    eip = 0x008be467   esp = 0xbff48b00   ebp = 0xbff49078   ebx = 0x03267d44
    esi = 0x0a287db8   edi = 0x09aa50c8
    Found by: call frame info
76  firefox-bin!main [nsBrowserApp.cpp : 158 + 0x17]
    eip = 0x08048d97   esp = 0xbff49080   ebp = 0xbff490f8   ebx = 0x0804c8bc
    esi = 0xbff49110   edi = 0x09aa50c8
    Found by: call frame info
77  libc-2.5.so + 0x15e9b
    eip = 0x05112e9c   esp = 0xbff49100   ebp = 0xbff49168
    Found by: previous frame's frame pointer
78  firefox-bin + 0x980
    eip = 0x08048981   esp = 0xbff49170   ebp = 0x00000000
    Found by: previous frame's frame pointer
79  firefox-bin!IsArg [nsBrowserApp.cpp : 97 + 0x5]
    eip = 0x08048aca   esp = 0xbff49174   ebp = 0x00000000
    Found by: stack scanning
80  ld-2.5.so + 0xe5ff
    eip = 0x004f2600   esp = 0xbff49188   ebp = 0x00000000
    Found by: stack scanning
81  ld-2.5.so + 0x1704a
    eip = 0x004fb04b   esp = 0xbff49190   ebp = 0x00000000
    Found by: stack scanning

Thread 1
 0  linux-gate.so + 0x402
    eip = 0x0058d402   esp = 0xb7f200c8   ebp = 0xb7f20128   ebx = 0x0000000f
    esi = 0xffffffff   edi = 0x00000000   eax = 0xfffffffc   ecx = 0x09ae6300
    edx = 0x000003ff   efl = 0x00200216
    Found by: given as instruction pointer in context
 1  0x9ad9a97
    eip = 0x09ad9a98   esp = 0xb7f20130   ebp = 0xb7f20158
    Found by: previous frame's frame pointer
 2  libxul.so!event_base_loop [event.c : 513 + 0x1b]
    eip = 0x01f4d99e   esp = 0xb7f20160   ebp = 0xb7f20198
    Found by: previous frame's frame pointer
 3  libxul.so!base::MessagePumpLibevent::Run [message_pump_libevent.cc : 330 + 0x15]
    eip = 0x01fc0271   esp = 0xb7f201a0   ebp = 0xb7f201f8   ebx = 0x03267d44
    Found by: call frame info
 4  libxul.so!MessageLoop::RunInternal [message_loop.cc : 219 + 0x20]
    eip = 0x01f6a34b   esp = 0xb7f20200   ebp = 0xb7f20228   ebx = 0x03267d44
    esi = 0x00000000
    Found by: call frame info
 5  libxul.so!MessageLoop::RunHandler [message_loop.cc : 202 + 0xa]
    eip = 0x01f6a2cb   esp = 0xb7f20230   ebp = 0xb7f20248   ebx = 0x03267d44
    esi = 0x00000000
    Found by: call frame info
 6  libxul.so!MessageLoop::Run [message_loop.cc : 176 + 0xa]
    eip = 0x01f6a26f   esp = 0xb7f20250   ebp = 0xb7f20278   ebx = 0x03267d44
    esi = 0x00000000
    Found by: call frame info
 7  libxul.so!base::Thread::ThreadMain [thread.cc : 156 + 0xd]
    eip = 0x01f8f28f   esp = 0xb7f20280   ebp = 0xb7f20388   ebx = 0x03267d44
    esi = 0x00000000
    Found by: call frame info
 8  libxul.so!ThreadFunc [platform_thread_posix.cc : 26 + 0x11]
    eip = 0x01fc07f6   esp = 0xb7f20390   ebp = 0xb7f203b8   ebx = 0x0054aff4
    esi = 0x00000000
    Found by: call frame info
 9  libpthread-2.5.so + 0x5831
    eip = 0x0053a832   esp = 0xb7f203c0   ebp = 0xb7f204a8   ebx = 0x0054aff4
    esi = 0x00000000
    Found by: call frame info
10  libc-2.5.so + 0xd1e0d
    eip = 0x051cee0e   esp = 0xb7f204b0   ebp = 0x00000000
    Found by: previous frame's frame pointer

Thread 2
 0  linux-gate.so + 0x402
    eip = 0x0058d402   esp = 0xb71db110   ebp = 0xb71db168   ebx = 0x09aec028
    esi = 0xb71db118   edi = 0x0000009f   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x0000009f   efl = 0x00200206
    Found by: given as instruction pointer in context
 1  0x2cb192f7
    eip = 0x2cb192f8   esp = 0xb71db170   ebp = 0x4cd42a62
    Found by: previous frame's frame pointer
 2  libnspr4.so!PR_WaitCondVar [ptsynch.c : 419 + 0x1d]
    eip = 0x00143445   esp = 0xb71db190   ebp = 0x4cd42a62
    Found by: stack scanning
 3  libxul.so!TimerThread::Run [TimerThread.cpp : 375 + 0x14]
    eip = 0x01f0bd0a   esp = 0xb71db1c0   ebp = 0x4cd42a62
    Found by: stack scanning
 4  libxul.so!nsCOMPtr<nsIRunnable>::assign_from_qi [nsCOMPtr.h : 1214 + 0x11]
    eip = 0x008cdcab   esp = 0xb71db1d0   ebp = 0x4cd42a62
    Found by: stack scanning
 5  libgtk-x11-2.0.so.0.1000.4 + 0x16fc7e
    eip = 0x037f0c7f   esp = 0xb71db1f8   ebp = 0x4cd42a62
    Found by: stack scanning

Thread 3
 0  linux-gate.so + 0x402
    eip = 0x0058d402   esp = 0xb67d9df4   ebp = 0xb67d9e08   ebx = 0xb67d9e24
    esi = 0x0012a0f8   edi = 0x05250ff4   eax = 0xfffffffc   ecx = 0x00000001
    edx = 0xffffffff   efl = 0x00200246
    Found by: given as instruction pointer in context
 1  libnspr4.so!_pr_poll_with_poll [ptio.c : 3917 + 0x18]
    eip = 0x00149045   esp = 0xb67d9e10   ebp = 0xb67da068
    Found by: previous frame's frame pointer
 2  libnspr4.so!PR_Poll [ptio.c : 4319 + 0x18]
    eip = 0x00149269   esp = 0xb67da070   ebp = 0xb67da088   ebx = 0x03267d44
    esi = 0x09c2fa00
    Found by: call frame info
 3  libxul.so!nsSocketTransportService::Poll [nsSocketTransportService2.cpp : 357 + 0x18]
    eip = 0x00940e6d   esp = 0xb67da090   ebp = 0xb67da0c8   ebx = 0x03267d44
    esi = 0x09c2fa00
    Found by: call frame info
 4  libxul.so!nsSocketTransportService::DoPollIteration [nsSocketTransportService2.cpp : 668 + 0x18]
    eip = 0x00941dc1   esp = 0xb67da0d0   ebp = 0xb67da148   ebx = 0x03267d44
    esi = 0x09c2fa00
    Found by: call frame info
 5  libxul.so!nsSocketTransportService::OnProcessNextEvent [nsSocketTransportService2.cpp : 547 + 0x12]
    eip = 0x009417ff   esp = 0xb67da150   ebp = 0xb67da178   ebx = 0x03267d44
    esi = 0x09c2fa00   edi = 0x00000001
    Found by: call frame info
 6  libxul.so!nsThread::ProcessNextEvent [nsThread.cpp : 576 + 0x55]
    eip = 0x01f02cc5   esp = 0xb67da180   ebp = 0xb67da1e8   ebx = 0x03267d44
    esi = 0x09c2fa00   edi = 0x00000001
    Found by: call frame info
 7  libxul.so!NS_ProcessNextEvent_P [nsThreadUtils.cpp : 250 + 0x1f]
    eip = 0x01e8ff91   esp = 0xb67da1f0   ebp = 0xb67da228   ebx = 0x03267d44
    esi = 0x00000001   edi = 0xb67dab90
    Found by: call frame info
 8  libxul.so!nsSocketTransportService::Run [nsSocketTransportService2.cpp : 589 + 0x12]
    eip = 0x0094198e   esp = 0xb67da230   ebp = 0xb67da278   ebx = 0x03267d44
    esi = 0x00000001   edi = 0xb67dab90
    Found by: call frame info
 9  libxul.so!nsThread::ProcessNextEvent [nsThread.cpp : 609 + 0x16]
    eip = 0x01f02dcd   esp = 0xb67da280   ebp = 0xb67da2e8   ebx = 0x03267d44
    esi = 0xb67da2b8   edi = 0xb67dab90
    Found by: call frame info
10  libxul.so!NS_ProcessNextEvent_P [nsThreadUtils.cpp : 250 + 0x1f]
    eip = 0x01e8ff91   esp = 0xb67da2f0   ebp = 0xb67da328   ebx = 0x03267d44
    esi = 0x00000000   edi = 0xb67dab90
    Found by: call frame info
11  libxul.so!nsThread::ThreadFunc [nsThread.cpp : 277 + 0x12]
    eip = 0x01f01db5   esp = 0xb67da330   ebp = 0xb67da388   ebx = 0x03267d44
    esi = 0x00000000   edi = 0xb67dab90
    Found by: call frame info
12  libnspr4.so!_pt_root [ptthread.c : 187 + 0x10]
    eip = 0x0014a783   esp = 0xb67da390   ebp = 0xb67da3b8   ebx = 0x0015f464
    esi = 0x00000000   edi = 0xb67dab90
    Found by: call frame info
13  libpthread-2.5.so + 0x5831
    eip = 0x0053a832   esp = 0xb67da3c0   ebp = 0xb67da4a8   ebx = 0x0054aff4
    esi = 0x00000000   edi = 0xb67dab90
    Found by: call frame info
14  libc-2.5.so + 0xd1e0d
    eip = 0x051cee0e   esp = 0xb67da4b0   ebp = 0x00000000
    Found by: previous frame's frame pointer

Thread 4
 0  linux-gate.so + 0x402
    eip = 0x0058d402   esp = 0xb5dd92dc   ebp = 0xb5dd9328   ebx = 0x09c6c918
    esi = 0x00000000   edi = 0x00000003   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x00000003   efl = 0x00200206
    Found by: given as instruction pointer in context
 1  libxul.so!js::GCHelperThread::threadLoop [jsgc.cpp : 1995 + 0x15]
    eip = 0x02169bb2   esp = 0xb5dd9330   ebp = 0xb5dd9358
    Found by: previous frame's frame pointer
 2  libxul.so!js::GCHelperThread::threadMain [jsgc.cpp : 1981 + 0x17]
    eip = 0x02169b66   esp = 0xb5dd9360   ebp = 0xb5dd9388   ebx = 0x0015f464
    Found by: call frame info
 3  libnspr4.so!_pt_root [ptthread.c : 187 + 0x10]
    eip = 0x0014a783   esp = 0xb5dd9390   ebp = 0xb5dd93b8   ebx = 0x0015f464
    Found by: call frame info
 4  libpthread-2.5.so + 0x5831
    eip = 0x0053a832   esp = 0xb5dd93c0   ebp = 0xb5dd94a8   ebx = 0x0054aff4
    Found by: call frame info
 5  libc-2.5.so + 0xd1e0d
    eip = 0x051cee0e   esp = 0xb5dd94b0   ebp = 0x00000000
    Found by: previous frame's frame pointer

Thread 5
 0  linux-gate.so + 0x402
    eip = 0x0058d402   esp = 0xb53d8290   ebp = 0xb53d82e8   ebx = 0x09c6d4a8
    esi = 0xb53d8298   edi = 0x00000017   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x00000017   efl = 0x00200202
    Found by: given as instruction pointer in context
 1  0x351b4e6f
    eip = 0x351b4e70   esp = 0xb53d82f0   ebp = 0x4cd42a62
    Found by: previous frame's frame pointer
 2  libc-2.5.so + 0x830e5
    eip = 0x051800e6   esp = 0xb53d82fc   ebp = 0x4cd42a62
    Found by: stack scanning
 3  libnspr4.so!PR_WaitCondVar [ptsynch.c : 419 + 0x1d]
    eip = 0x00143445   esp = 0xb53d8310   ebp = 0x4cd42a62
    Found by: stack scanning
 4  libxul.so!XPCJSRuntime::WatchdogMain [xpcjsruntime.cpp : 861 + 0x17]
    eip = 0x01705ce1   esp = 0xb53d8340   ebp = 0x4cd42a62
    Found by: stack scanning

Thread 6
 0  linux-gate.so + 0x402
    eip = 0x0058d402   esp = 0xb439f0e0   ebp = 0xb439f138   ebx = 0x0a02a7e8
    esi = 0xb439f0e8   edi = 0x00000047   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x00000047   efl = 0x00200206
    Found by: given as instruction pointer in context
 1  0x3567f387
    eip = 0x3567f388   esp = 0xb439f140   ebp = 0x4cd42a9b
    Found by: previous frame's frame pointer
 2  libnspr4.so!PR_WaitCondVar [ptsynch.c : 419 + 0x1d]
    eip = 0x00143445   esp = 0xb439f160   ebp = 0x4cd42a9b
    Found by: stack scanning
 3  libxul.so!nsEventQueue::GetEvent [nsEventQueue.cpp : 99 + 0xa]
    eip = 0x01f009b9   esp = 0xb439f170   ebp = 0x4cd42a9b
    Found by: stack scanning
 4  libgtk-x11-2.0.so.0.1000.4 + 0x2b78f3
    eip = 0x039388f4   esp = 0xb439f17c   ebp = 0x4cd42a9b
    Found by: stack scanning
 5  libnspr4.so!PR_Wait [ptsynch.c : 614 + 0x14]
    eip = 0x00143c13   esp = 0xb439f190   ebp = 0x4cd42a9b
    Found by: stack scanning
 6  libxul.so!nsAutoMonitor::Wait [nsAutoLock.h : 346 + 0x14]
    eip = 0x009d225d   esp = 0xb439f1c0   ebp = 0x4cd42a9b
    Found by: stack scanning
 7  libxul.so!nsThreadPool::Run [nsThreadPool.cpp : 212 + 0x11]
    eip = 0x01f069ea   esp = 0xb439f1e0   ebp = 0x4cd42a9b
    Found by: stack scanning

Thread 7
 0  linux-gate.so + 0x402
    eip = 0x0058d402   esp = 0xb398c16c   ebp = 0xb398c1b8   ebx = 0x0a29a810
    esi = 0x00000000   edi = 0x0000000d   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x0000000d   efl = 0x00200212
    Found by: given as instruction pointer in context
 1  libnspr4.so!PR_Wait [ptsynch.c : 614 + 0x14]
    eip = 0x00143c13   esp = 0xb398c1c0   ebp = 0xb398c1e8
    Found by: previous frame's frame pointer
 2  libxul.so!nsAutoMonitor::Wait [nsAutoLock.h : 346 + 0x14]
    eip = 0x009d225d   esp = 0xb398c1f0   ebp = 0xb398c208   ebx = 0x03267d44
    Found by: call frame info
 3  libxul.so!nsEventQueue::GetEvent [nsEventQueue.cpp : 85 + 0x12]
    eip = 0x01f0090d   esp = 0xb398c210   ebp = 0xb398c258   ebx = 0x03267d44
    Found by: call frame info
 4  libxul.so!nsThread::nsChainedEventQueue::GetEvent [nsThread.h : 112 + 0x1b]
    eip = 0x01f03642   esp = 0xb398c260   ebp = 0xb398c278   ebx = 0x03267d44
    esi = 0xb398c2b8   edi = 0x016d6bd3
    Found by: call frame info
 5  libxul.so!nsThread::ProcessNextEvent [nsThread.cpp : 592 + 0x5b]
    eip = 0x01f02d4d   esp = 0xb398c280   ebp = 0xb398c2e8   ebx = 0x03267d44
    esi = 0xb398c2b8   edi = 0x016d6bd3
    Found by: call frame info
 6  libxul.so!NS_ProcessNextEvent_P [nsThreadUtils.cpp : 250 + 0x1f]
    eip = 0x01e8ff91   esp = 0xb398c2f0   ebp = 0xb398c328   ebx = 0x03267d44
    esi = 0x00000000   edi = 0xb398cb90
    Found by: call frame info
 7  libxul.so!nsThread::ThreadFunc [nsThread.cpp : 277 + 0x12]
    eip = 0x01f01db5   esp = 0xb398c330   ebp = 0xb398c388   ebx = 0x03267d44
    esi = 0x00000000   edi = 0xb398cb90
    Found by: call frame info
 8  libnspr4.so!_pt_root [ptthread.c : 187 + 0x10]
    eip = 0x0014a783   esp = 0xb398c390   ebp = 0xb398c3b8   ebx = 0x0015f464
    esi = 0x00000000   edi = 0xb398cb90
    Found by: call frame info
 9  libpthread-2.5.so + 0x5831
    eip = 0x0053a832   esp = 0xb398c3c0   ebp = 0xb398c4a8   ebx = 0x0054aff4
    esi = 0x00000000   edi = 0xb398cb90
    Found by: call frame info
10  libc-2.5.so + 0xd1e0d
    eip = 0x051cee0e   esp = 0xb398c4b0   ebp = 0x00000000
    Found by: previous frame's frame pointer

Thread 8
 0  linux-gate.so + 0x402
    eip = 0x0058d402   esp = 0xb2f8b16c   ebp = 0xb2f8b1b8   ebx = 0x0a518ec8
    esi = 0x00000000   edi = 0x0000001b   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x0000001b   efl = 0x00200202
    Found by: given as instruction pointer in context
 1  libnspr4.so!PR_Wait [ptsynch.c : 614 + 0x14]
    eip = 0x00143c13   esp = 0xb2f8b1c0   ebp = 0xb2f8b1e8
    Found by: previous frame's frame pointer
 2  libxul.so!nsAutoMonitor::Wait [nsAutoLock.h : 346 + 0x14]
    eip = 0x009d225d   esp = 0xb2f8b1f0   ebp = 0xb2f8b208   ebx = 0x03267d44
    Found by: call frame info
 3  libxul.so!nsEventQueue::GetEvent [nsEventQueue.cpp : 85 + 0x12]
    eip = 0x01f0090d   esp = 0xb2f8b210   ebp = 0xb2f8b258   ebx = 0x03267d44
    Found by: call frame info
 4  libxul.so!nsThread::nsChainedEventQueue::GetEvent [nsThread.h : 112 + 0x1b]
    eip = 0x01f03642   esp = 0xb2f8b260   ebp = 0xb2f8b278   ebx = 0x03267d44
    esi = 0xb2f8b2b8   edi = 0x016d6bd3
    Found by: call frame info
 5  libxul.so!nsThread::ProcessNextEvent [nsThread.cpp : 592 + 0x5b]
    eip = 0x01f02d4d   esp = 0xb2f8b280   ebp = 0xb2f8b2e8   ebx = 0x03267d44
    esi = 0xb2f8b2b8   edi = 0x016d6bd3
    Found by: call frame info
 6  libxul.so!NS_ProcessNextEvent_P [nsThreadUtils.cpp : 250 + 0x1f]
    eip = 0x01e8ff91   esp = 0xb2f8b2f0   ebp = 0xb2f8b328   ebx = 0x03267d44
    esi = 0x00000000   edi = 0xb2f8bb90
    Found by: call frame info
 7  libxul.so!nsThread::ThreadFunc [nsThread.cpp : 277 + 0x12]
    eip = 0x01f01db5   esp = 0xb2f8b330   ebp = 0xb2f8b388   ebx = 0x03267d44
    esi = 0x00000000   edi = 0xb2f8bb90
    Found by: call frame info
 8  libnspr4.so!_pt_root [ptthread.c : 187 + 0x10]
    eip = 0x0014a783   esp = 0xb2f8b390   ebp = 0xb2f8b3b8   ebx = 0x0015f464
    esi = 0x00000000   edi = 0xb2f8bb90
    Found by: call frame info
 9  libpthread-2.5.so + 0x5831
    eip = 0x0053a832   esp = 0xb2f8b3c0   ebp = 0xb2f8b4a8   ebx = 0x0054aff4
    esi = 0x00000000   edi = 0xb2f8bb90
    Found by: call frame info
10  libc-2.5.so + 0xd1e0d
    eip = 0x051cee0e   esp = 0xb2f8b4b0   ebp = 0x00000000
    Found by: previous frame's frame pointer

Thread 9
 0  linux-gate.so + 0x402
    eip = 0x0058d402   esp = 0xb2358250   ebp = 0xb23582a8   ebx = 0x09c55a48
    esi = 0xb2358258   edi = 0x00000041   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x00000041   efl = 0x00000206
    Found by: given as instruction pointer in context
 1  0x1ad5ef1f
    eip = 0x1ad5ef20   esp = 0xb23582b0   ebp = 0x4cd42b8e
    Found by: previous frame's frame pointer
 2  libnspr4.so!PR_WaitCondVar [ptsynch.c : 419 + 0x1d]
    eip = 0x00143445   esp = 0xb23582d0   ebp = 0x4cd42b8e
    Found by: stack scanning
 3  libxul.so!nsHostResolver::GetHostToLookup [nsHostResolver.cpp : 777 + 0x14]
    eip = 0x0095722e   esp = 0xb2358300   ebp = 0x4cd42b8e
    Found by: stack scanning

Thread 10
 0  linux-gate.so + 0x402
    eip = 0x0058d402   esp = 0xb195716c   ebp = 0xb19571b8   ebx = 0x0a5aac98
    esi = 0x00000000   edi = 0x000000df   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x000000df   efl = 0x00000202
    Found by: given as instruction pointer in context
 1  libnspr4.so!PR_Wait [ptsynch.c : 614 + 0x14]
    eip = 0x00143c13   esp = 0xb19571c0   ebp = 0xb19571e8
    Found by: previous frame's frame pointer
 2  libxul.so!nsAutoMonitor::Wait [nsAutoLock.h : 346 + 0x14]
    eip = 0x009d225d   esp = 0xb19571f0   ebp = 0xb1957208   ebx = 0x03267d44
    Found by: call frame info
 3  libxul.so!nsEventQueue::GetEvent [nsEventQueue.cpp : 85 + 0x12]
    eip = 0x01f0090d   esp = 0xb1957210   ebp = 0xb1957258   ebx = 0x03267d44
    Found by: call frame info
 4  libxul.so!nsThread::nsChainedEventQueue::GetEvent [nsThread.h : 112 + 0x1b]
    eip = 0x01f03642   esp = 0xb1957260   ebp = 0xb1957278   ebx = 0x03267d44
    esi = 0xb19572b8   edi = 0x016d6bd3
    Found by: call frame info
 5  libxul.so!nsThread::ProcessNextEvent [nsThread.cpp : 592 + 0x5b]
    eip = 0x01f02d4d   esp = 0xb1957280   ebp = 0xb19572e8   ebx = 0x03267d44
    esi = 0xb19572b8   edi = 0x016d6bd3
    Found by: call frame info
 6  libxul.so!NS_ProcessNextEvent_P [nsThreadUtils.cpp : 250 + 0x1f]
    eip = 0x01e8ff91   esp = 0xb19572f0   ebp = 0xb1957328   ebx = 0x03267d44
    esi = 0x00000000   edi = 0xb1957b90
    Found by: call frame info
 7  libxul.so!nsThread::ThreadFunc [nsThread.cpp : 277 + 0x12]
    eip = 0x01f01db5   esp = 0xb1957330   ebp = 0xb1957388   ebx = 0x03267d44
    esi = 0x00000000   edi = 0xb1957b90
    Found by: call frame info
 8  libnspr4.so!_pt_root [ptthread.c : 187 + 0x10]
    eip = 0x0014a783   esp = 0xb1957390   ebp = 0xb19573b8   ebx = 0x0015f464
    esi = 0x00000000   edi = 0xb1957b90
    Found by: call frame info
 9  libpthread-2.5.so + 0x5831
    eip = 0x0053a832   esp = 0xb19573c0   ebp = 0xb19574a8   ebx = 0x0054aff4
    esi = 0x00000000   edi = 0xb1957b90
    Found by: call frame info
10  libc-2.5.so + 0xd1e0d
    eip = 0x051cee0e   esp = 0xb19574b0   ebp = 0x00000000
    Found by: previous frame's frame pointer

Thread 11
 0  linux-gate.so + 0x402
    eip = 0x0058d402   esp = 0xb0f5626c   ebp = 0xb0f562b8   ebx = 0x0a861bb0
    esi = 0x00000000   edi = 0x00000001   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x00000001   efl = 0x00000212
    Found by: given as instruction pointer in context
 1  libxul.so!nsSSLThread::Run [nsSSLThread.cpp : 980 + 0x15]
    eip = 0x01944830   esp = 0xb0f562c0   ebp = 0xb0f56358
    Found by: previous frame's frame pointer
 2  libxul.so!nsPSMBackgroundThread::nsThreadRunner [nsPSMBackgroundThread.cpp : 44 + 0xe]
    eip = 0x01942aaf   esp = 0xb0f56360   ebp = 0xb0f56388   ebx = 0x0015f464
    esi = 0x00000000
    Found by: call frame info
 3  libnspr4.so!_pt_root [ptthread.c : 187 + 0x10]
    eip = 0x0014a783   esp = 0xb0f56390   ebp = 0xb0f563b8   ebx = 0x0015f464
    esi = 0x00000000
    Found by: call frame info
 4  libpthread-2.5.so + 0x5831
    eip = 0x0053a832   esp = 0xb0f563c0   ebp = 0xb0f564a8   ebx = 0x0054aff4
    esi = 0x00000000
    Found by: call frame info
 5  libc-2.5.so + 0xd1e0d
    eip = 0x051cee0e   esp = 0xb0f564b0   ebp = 0x00000000
    Found by: previous frame's frame pointer

Thread 12
 0  linux-gate.so + 0x402
    eip = 0x0058d402   esp = 0xb05552ac   ebp = 0xb05552f8   ebx = 0x0a861e28
    esi = 0x00000000   edi = 0x00000001   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x00000001   efl = 0x00000206
    Found by: given as instruction pointer in context
 1  libxul.so!nsCertVerificationThread::Run [nsCertVerificationThread.cpp : 138 + 0x15]
    eip = 0x0194555a   esp = 0xb0555300   ebp = 0xb0555358
    Found by: previous frame's frame pointer
 2  libxul.so!nsPSMBackgroundThread::nsThreadRunner [nsPSMBackgroundThread.cpp : 44 + 0xe]
    eip = 0x01942aaf   esp = 0xb0555360   ebp = 0xb0555388   ebx = 0x0015f464
    esi = 0x00000000
    Found by: call frame info
 3  libnspr4.so!_pt_root [ptthread.c : 187 + 0x10]
    eip = 0x0014a783   esp = 0xb0555390   ebp = 0xb05553b8   ebx = 0x0015f464
    esi = 0x00000000
    Found by: call frame info
 4  libpthread-2.5.so + 0x5831
    eip = 0x0053a832   esp = 0xb05553c0   ebp = 0xb05554a8   ebx = 0x0054aff4
    esi = 0x00000000
    Found by: call frame info
 5  libc-2.5.so + 0xd1e0d
    eip = 0x051cee0e   esp = 0xb05554b0   ebp = 0x00000000
    Found by: previous frame's frame pointer

Thread 13
 0  linux-gate.so + 0x402
    eip = 0x0058d402   esp = 0xafb5416c   ebp = 0xafb541b8   ebx = 0x0a862618
    esi = 0x00000000   edi = 0x00000001   eax = 0xfffffffc   ecx = 0x00000080
    edx = 0x00000001   efl = 0x00000206
    Found by: given as instruction pointer in context
 1  libnspr4.so!PR_Wait [ptsynch.c : 614 + 0x14]
    eip = 0x00143c13   esp = 0xafb541c0   ebp = 0xafb541e8
    Found by: previous frame's frame pointer
 2  libxul.so!nsAutoMonitor::Wait [nsAutoLock.h : 346 + 0x14]
    eip = 0x009d225d   esp = 0xafb541f0   ebp = 0xafb54208   ebx = 0x03267d44
    Found by: call frame info
 3  libxul.so!nsEventQueue::GetEvent [nsEventQueue.cpp : 85 + 0x12]
    eip = 0x01f0090d   esp = 0xafb54210   ebp = 0xafb54258   ebx = 0x03267d44
    Found by: call frame info
 4  libxul.so!nsThread::nsChainedEventQueue::GetEvent [nsThread.h : 112 + 0x1b]
    eip = 0x01f03642   esp = 0xafb54260   ebp = 0xafb54278   ebx = 0x03267d44
    esi = 0xafb542b8   edi = 0x016d6bd3
    Found by: call frame info
 5  libxul.so!nsThread::ProcessNextEvent [nsThread.cpp : 592 + 0x5b]
    eip = 0x01f02d4d   esp = 0xafb54280   ebp = 0xafb542e8   ebx = 0x03267d44
    esi = 0xafb542b8   edi = 0x016d6bd3
    Found by: call frame info
 6  libxul.so!NS_ProcessNextEvent_P [nsThreadUtils.cpp : 250 + 0x1f]
    eip = 0x01e8ff91   esp = 0xafb542f0   ebp = 0xafb54328   ebx = 0x03267d44
    esi = 0x00000000   edi = 0xafb54b90
    Found by: call frame info
 7  libxul.so!nsThread::ThreadFunc [nsThread.cpp : 277 + 0x12]
    eip = 0x01f01db5   esp = 0xafb54330   ebp = 0xafb54388   ebx = 0x03267d44
    esi = 0x00000000   edi = 0xafb54b90
    Found by: call frame info
 8  libnspr4.so!_pt_root [ptthread.c : 187 + 0x10]
    eip = 0x0014a783   esp = 0xafb54390   ebp = 0xafb543b8   ebx = 0x0015f464
    esi = 0x00000000   edi = 0xafb54b90
    Found by: call frame info
 9  libpthread-2.5.so + 0x5831
    eip = 0x0053a832   esp = 0xafb543c0   ebp = 0xafb544a8   ebx = 0x0054aff4
    esi = 0x00000000   edi = 0xafb54b90
    Found by: call frame info
10  libc-2.5.so + 0xd1e0d
    eip = 0x051cee0e   esp = 0xafb544b0   ebp = 0x00000000
    Found by: previous frame's frame pointer

Thread 14
 0  linux-gate.so + 0x402
    eip = 0x0058d402   esp = 0xae3cd344   ebp = 0xae3cd358   ebx = 0xae3cd37c
    esi = 0x00000000   edi = 0x05250ff4   eax = 0xfffffffc   ecx = 0x00000002
    edx = 0xffffffff   efl = 0x00200246
    Found by: given as instruction pointer in context
 1  libxul.so!google_breakpad::CrashGenerationServer::Run [crash_generation_server.cc : 278 + 0x1a]
    eip = 0x008dec40   esp = 0xae3cd360   ebp = 0xae3cd398
    Found by: previous frame's frame pointer
 2  libxul.so!google_breakpad::CrashGenerationServer::ThreadMain [crash_generation_server.cc : 462 + 0xa]
    eip = 0x008df391   esp = 0xae3cd3a0   ebp = 0xae3cd3b8   ebx = 0x0054aff4
    Found by: call frame info
 3  libpthread-2.5.so + 0x5831
    eip = 0x0053a832   esp = 0xae3cd3c0   ebp = 0xae3cd4a8   ebx = 0x0054aff4
    Found by: call frame info
 4  libc-2.5.so + 0xd1e0d
    eip = 0x051cee0e   esp = 0xae3cd4b0   ebp = 0x00000000
    Found by: previous frame's frame pointer

Loaded modules:
0x00110000 - 0x00112fff  libxpcom.so  ???  (main)
0x00114000 - 0x00115fff  libmozalloc.so  ???
0x00117000 - 0x00119fff  libplds4.so  ???
0x0011b000 - 0x0015efff  libnspr4.so  ???
0x00162000 - 0x0017bfff  libatk-1.0.so.0.1212.0  ???
0x0017e000 - 0x00207fff  libgdk-x11-2.0.so.0.1000.4  ???
0x0020b000 - 0x00220fff  libgdk_pixbuf-2.0.so.0.1000.4  ???
0x00222000 - 0x00229fff  libpangocairo-1.0.so.0.1400.9  ???
0x0022b000 - 0x00267fff  libpango-1.0.so.0.1400.9  ???
0x0026a000 - 0x002d5fff  libcairo.so.2.9.2  ???
0x002d8000 - 0x00315fff  libgobject-2.0.so.0.1200.3  ???
0x00317000 - 0x00318fff  libgmodule-2.0.so.0.1200.3  ???
0x0031a000 - 0x003b6fff  libglib-2.0.so.0.1200.3  ???
0x003b8000 - 0x003c2fff  libgcc_s-4.1.2-20080825.so.1  ???
0x003c4000 - 0x003f1fff  libsmime3.so  ???
0x003f5000 - 0x00411fff  libnssutil3.so  ???
0x00415000 - 0x0041cfff  libXrender.so.1.3.0  ???
0x0041e000 - 0x0042cfff  libXext.so.6.4.0  ???
0x0042e000 - 0x0042efff  pango-arabic-lang.so  ???
0x0042f000 - 0x0042ffff  pango-arabic-lang.so  ???
0x00430000 - 0x00433fff  libplc4.so  ???
0x00435000 - 0x0047dfff  libssl3.so  ???
0x00480000 - 0x004a6fff  libfontconfig.so.1.1.0  ???
0x004af000 - 0x004cbfff  libdbus-glib-1.so.2.1.0  ???
0x004cd000 - 0x004d0fff  libgthread-2.0.so.0.1200.3  ???
0x004d2000 - 0x004d3fff  libXinerama.so.1.0.0  ???
0x004d5000 - 0x004dbfff  libXi.so.6.0.0  ???
0x004dd000 - 0x004dffff  libXrandr.so.2.0.0  ???
0x004e1000 - 0x004e2fff  libXau.so.6.0.0  ???
0x004e4000 - 0x004fefff  ld-2.5.so  ???
0x00503000 - 0x00529fff  libm-2.5.so  ???
0x0052e000 - 0x00530fff  libdl-2.5.so  ???
0x00535000 - 0x00549fff  libpthread-2.5.so  ???
0x0054e000 - 0x00556fff  libXcursor.so.1.0.2  ???
0x00558000 - 0x0055bfff  libXfixes.so.3.1.0  ???
0x0055d000 - 0x00561fff  libXdmcp.so.6.0.0  ???
0x00565000 - 0x0056bfff  librt-2.5.so  ???
0x0056e000 - 0x0057ffff  libz.so.1.2.3  ???
0x00581000 - 0x00583fff  libcap.so.1.10  ???
0x00585000 - 0x00585fff  ISO8859-1.so  ???
0x00586000 - 0x00587fff  ISO8859-1.so  ???
0x00588000 - 0x0058bfff  libORBitCosNaming-2.so.0.1.0  ???
0x0058d000 - 0x0058dfff  linux-gate.so  ???
0x0058e000 - 0x03144fff  libxul.so  ???
0x03681000 - 0x03a11fff  libgtk-x11-2.0.so.0.1000.4  ???
0x03a19000 - 0x03a45fff  libpangoft2-1.0.so.0.1400.9  ???
0x03a47000 - 0x03a65fff  libexpat.so.0.5.0  ???
0x03a68000 - 0x03a7cfff  libnsl-2.5.so  ???
0x03a81000 - 0x03a88fff  libSM.so.6.0.0  ???
0x03a8a000 - 0x03b19fff  libgnomeui-2.so.0.1600.0  ???
0x03b1e000 - 0x03b81fff  libbonoboui-2.so.0.0.0  ???
0x03b85000 - 0x03bb0fff  libgnomecanvas-2.so.0.1400.0  ???
0x03bb2000 - 0x03c11fff  libgnomevfs-2.so.0.1600.2  ???
0x03c15000 - 0x03c47fff  libgconf-2.so.4.1.0  ???
0x03c4b000 - 0x03c6bfff  libjpeg.so.62.0.0  ???
0x03c6d000 - 0x03c73fff  libpopt.so.0.0.0  ???
0x03c75000 - 0x03c9cfff  libaudiofile.so.0.0.2  ???
0x03ca0000 - 0x03ce3fff  libssl.so.0.9.8e  ???
0x03ce8000 - 0x03cf2fff  libavahi-common.so.3.4.3  ???
0x03cf4000 - 0x03d03fff  libresolv-2.5.so  ???
0x03d08000 - 0x03d1dfff  libselinux.so.1  ???
0x03d20000 - 0x03d21fff  libutil-2.5.so  ???
0x03d24000 - 0x03d50fff  libgssapi_krb5.so.2.2  ???
0x03d52000 - 0x03de4fff  libkrb5.so.3.3  ???
0x03de8000 - 0x03e0cfff  libk5crypto.so.3.1  ???
0x03e0e000 - 0x03e0ffff  libkeyutils-1.2.so  ???
0x03e15000 - 0x03e28fff  libmozgnome.so  ???
0x03e2a000 - 0x03e2ffff  libnotify.so.1.1.0  ???
0x03e31000 - 0x03e3dfff  libdbusservice.so  ???
0x03e43000 - 0x03e44fff  libavahi-glib.so.1.0.1  ???
0x03e46000 - 0x03e80fff  libsepol.so.1  ???
0x03e8c000 - 0x03edefff  libbrowsercomps.so  ???
0x03ee1000 - 0x03ef1fff  libclearlooks.so  ???
0x03ef3000 - 0x03ef6fff  libpixbufloader-png.so  ???
0x03f45000 - 0x03f5bfff  libICE.so.6.3.0  ???
0x03f5f000 - 0x03fa3fff  libsoftokn3.so  ???
0x03fa5000 - 0x03ffefff  libfreebl3.so  ???
0x04004000 - 0x04063fff  libnssckbi.so  ???
0x04140000 - 0x0414efff  libavahi-client.so.3.2.1  ???
0x0422a000 - 0x0422bfff  UTF-16.so  ???
0x04257000 - 0x04382fff  libxml2.so.2.6.26  ???
0x04921000 - 0x04924fff  libnss_dns-2.5.so  ???
0x04bed000 - 0x04c11fff  libpng12.so.0.10.0  ???
0x04d5c000 - 0x04d5dfff  pango-hangul-fc.so  ???
0x04ff0000 - 0x04ff7fff  libkrb5support.so.0.1  ???
0x050fd000 - 0x0524efff  libc-2.5.so  ???
0x056e9000 - 0x05742fff  libbonobo-2.so.0.0.0  ???
0x0578b000 - 0x05807fff  libfreetype.so.6.3.10  ???
0x0590c000 - 0x05917fff  libgnome-keyring.so.0.0.1  ???
0x06329000 - 0x06427fff  libX11.so.6.2.0  ???
0x06522000 - 0x06523fff  pango-syriac-fc.so  ???
0x06565000 - 0x06593fff  libnssdbm3.so  ???
0x06620000 - 0x06789fff  libnss3.so  ???
0x06931000 - 0x06932fff  pango-basic-fc.so  ???
0x06a8d000 - 0x06b6cfff  libmozsqlite3.so  ???
0x07284000 - 0x072c0fff  libdbus-1.so.3.4.0  ???
0x075fe000 - 0x07607fff  libnss_files-2.5.so  ???
0x076f0000 - 0x076f2fff  pango-hebrew-fc.so  ???
0x07868000 - 0x07869fff  libcom_err.so.2.1  ???
0x0796e000 - 0x07a47fff  libasound.so.2.0.0  ???
0x07bcc000 - 0x07cf5fff  libcrypto.so.0.9.8e  ???
0x07db3000 - 0x07db4fff  libXss.so.1.0.0  ???
0x07dd7000 - 0x07debfff  libgnome-2.so.0.1600.0  ???
0x08048000 - 0x0804bfff  firefox-bin  ???
0x0808f000 - 0x08097fff  libesd.so.0.2.36  ???
0x08161000 - 0x08174fff  libbonobo-activation.so.4.0.0  ???
0x08a46000 - 0x08a5bfff  libart_lgpl_2.so.2.3.17  ???
0x08c1c000 - 0x08c1efff  pango-arabic-fc.so  ???
0x08cf1000 - 0x08d04fff  libnkgnomevfs.so  ???
0x093d5000 - 0x09422fff  libORBit-2.so.0.1.0  ???
0x096af000 - 0x09702fff  libXt.so.6.0.0  ???
0x097db000 - 0x098bafff  libstdc++.so.6.0.8  ???
0xad8a4000 - 0xad8c7fff  n021003l.pfb  ???
0xad8c8000 - 0xad941fff  6x13.pcf  ???
0xad942000 - 0xad9ccfff  9x15.pcf  ???
0xae3ce000 - 0xae46dfff  10x20.pcf  ???
0xae46e000 - 0xaef99fff  libflashplayer.so  ???
0xb2359000 - 0xb2392fff  DejaVuLGCSansMono.ttf  ???
0xb2393000 - 0xb23fffff  DejaVuLGCSans.ttf  ???
0xb251c000 - 0xb2556fff  6x13B.pcf  ???
0xb2557000 - 0xb258afff  DejaVuLGCSerif.ttf  ???
0xb398d000 - 0xb399efff  spider.jar  ???
0xb43a0000 - 0xb43fffff  SYSV00000000 (deleted)  ???
0xb451d000 - 0xb454dfff  DejaVuLGCSerif-Bold.ttf  ???
0xb454e000 - 0xb45bafff  DejaVuLGCSans.ttf  ???
0xb45bb000 - 0xb45bcfff  87f5e051180a7a75f16eb6fe7dbd3749-x86.cache-2  ???
0xb45bd000 - 0xb45c2fff  b79f3aaa7d385a141ab53ec885cc22a8-x86.cache-2  ???
0xb45c3000 - 0xb45c8fff  7ddba6133ef499da58de5e8c586d3b75-x86.cache-2  ???
0xb45c9000 - 0xb45cafff  e3ead4b767b8819993a6fa3ae306afa9-x86.cache-2  ???
0xb45cb000 - 0xb45d2fff  e19de935dec46bbf3ed114ee4965548a-x86.cache-2  ???
0xb45d3000 - 0xb45d7fff  beeeeb3dfe132a8a0633a017c99ce0c0-x86.cache-2  ???
0xb71dc000 - 0xb751ffff  omni.jar  ???
0xb7f35000 - 0xb7f3bfff  gconv-modules.cache  ???

 EXIT STATUS: NORMAL (254.673931 seconds)
""",
"""
Operating system: Mac OS X
                  10.5.8 9L34
CPU: ppc
     2 CPUs

Crash reason:  EXC_BAD_ACCESS / KERN_PROTECTION_FAILURE
Crash address: 0x0

Thread 0 (crashed)
 0  QuickTime Plugin + 0x12570
   srr0 = 0x111c1570    r1 = 0xbfff1b30
    Found by: given as instruction pointer in context
 1  QuickTime Plugin + 0x20e64
   srr0 = 0x111cfe68    r1 = 0xbfff1ba0
    Found by: previous frame's frame pointer
 2  QuickTime Plugin + 0x150fc
   srr0 = 0x111c4100    r1 = 0xbfff1c00
    Found by: previous frame's frame pointer
 3  QuickTime Plugin + 0x17e84
   srr0 = 0x111c6e88    r1 = 0xbfff1ce0
    Found by: previous frame's frame pointer
 4  QuickTime Plugin + 0x180c0
   srr0 = 0x111c70c4    r1 = 0xbfff1ea0
    Found by: previous frame's frame pointer
 5  QuickTime Plugin + 0x18b08
   srr0 = 0x111c7b0c    r1 = 0xbfff2240
    Found by: previous frame's frame pointer
 6  QuickTime Plugin + 0x1ab54
   srr0 = 0x111c9b58    r1 = 0xbfff2310
    Found by: previous frame's frame pointer
 7  QuickTime Plugin + 0x10b84
   srr0 = 0x111bfb88    r1 = 0xbfff23b0
    Found by: previous frame's frame pointer
 8  XUL + 0x13de6a8
   srr0 = 0x049f16ac    r1 = 0xbfff2410
    Found by: previous frame's frame pointer
 9  XUL + 0x13f1374
   srr0 = 0x04a04378    r1 = 0xbfff24e0
    Found by: previous frame's frame pointer
10  XUL + 0x1ecb2c
   srr0 = 0x037ffb30    r1 = 0xbfff25c0
    Found by: previous frame's frame pointer
11  XUL + 0x2ceedc
   srr0 = 0x038e1ee0    r1 = 0xbfff2650
    Found by: previous frame's frame pointer
12  XUL + 0x1a40cc
   srr0 = 0x037b70d0    r1 = 0xbfff26f0
    Found by: previous frame's frame pointer
13  XUL + 0x1a4858
   srr0 = 0x037b785c    r1 = 0xbfff27c0
    Found by: previous frame's frame pointer
14  XUL + 0x1854838
   srr0 = 0x04e6783c    r1 = 0xbfff2820
    Found by: previous frame's frame pointer
15  XUL + 0x1896e38
   srr0 = 0x04ea9e3c    r1 = 0xbfff2870
    Found by: previous frame's frame pointer
16  XUL + 0x17fb394
   srr0 = 0x04e0e398    r1 = 0xbfff2910
    Found by: previous frame's frame pointer
17  XUL + 0x189775c
   srr0 = 0x04eaa760    r1 = 0xbfff2970
    Found by: previous frame's frame pointer
18  XUL + 0x18bed60
   srr0 = 0x04ed1d64    r1 = 0xbfff2a00
    Found by: previous frame's frame pointer
19  XUL + 0x18be414
   srr0 = 0x04ed1418    r1 = 0xbfff2ab0
    Found by: previous frame's frame pointer
20  XUL + 0x18a6764
   srr0 = 0x04eb9768    r1 = 0xbfff2b00
    Found by: previous frame's frame pointer
21  XUL + 0x1896e38
   srr0 = 0x04ea9e3c    r1 = 0xbfff2b50
    Found by: previous frame's frame pointer
22  XUL + 0x17fb394
   srr0 = 0x04e0e398    r1 = 0xbfff2bf0
    Found by: previous frame's frame pointer
23  XUL + 0x12a3090
   srr0 = 0x048b6094    r1 = 0xbfff2c50
    Found by: previous frame's frame pointer
24  XUL + 0x12992dc
   srr0 = 0x048ac2e0    r1 = 0xbfff2d10
    Found by: previous frame's frame pointer
25  XUL + 0x12d4ae0
   srr0 = 0x048e7ae4    r1 = 0xbfff2d60
    Found by: previous frame's frame pointer
26  XUL + 0x122b988
   srr0 = 0x0483e98c    r1 = 0xbfff2e00
    Found by: previous frame's frame pointer
27  XUL + 0x122d814
   srr0 = 0x04840818    r1 = 0xbfff3260
    Found by: previous frame's frame pointer
28  XUL + 0xcaa118
   srr0 = 0x042bd11c    r1 = 0xbfff32d0
    Found by: previous frame's frame pointer
29  XUL + 0xcab20c
   srr0 = 0x042be210    r1 = 0xbfff34c0
    Found by: previous frame's frame pointer
30  XUL + 0x18bed60
   srr0 = 0x04ed1d64    r1 = 0xbfff3530
    Found by: previous frame's frame pointer
31  XUL + 0x18be414
   srr0 = 0x04ed1418    r1 = 0xbfff35f0
    Found by: previous frame's frame pointer
32  XUL + 0xf36fc
   srr0 = 0x03706700    r1 = 0xbfff3640
    Found by: previous frame's frame pointer
33  XUL + 0x102c90
   srr0 = 0x03715c94    r1 = 0xbfff3a00
    Found by: previous frame's frame pointer
34  libmozjs.dylib + 0xb1f0c
   srr0 = 0x0029cf10    r1 = 0xbfff3b00
    Found by: previous frame's frame pointer
35  libmozjs.dylib + 0x9d0c8
   srr0 = 0x002880cc    r1 = 0xbfff3c10
    Found by: previous frame's frame pointer
36  libmozjs.dylib + 0xb022c
   srr0 = 0x0029b230    r1 = 0xbfff4870
    Found by: previous frame's frame pointer
37  libmozjs.dylib + 0xd7db0
   srr0 = 0x002c2db4    r1 = 0xbfff4940
    Found by: previous frame's frame pointer
38  libmozjs.dylib + 0xb1f0c
   srr0 = 0x0029cf10    r1 = 0xbfff4a60
    Found by: previous frame's frame pointer
39  libmozjs.dylib + 0x9d0c8
   srr0 = 0x002880cc    r1 = 0xbfff4b70
    Found by: previous frame's frame pointer
40  libmozjs.dylib + 0xb022c
   srr0 = 0x0029b230    r1 = 0xbfff57d0
    Found by: previous frame's frame pointer
41  libmozjs.dylib + 0x1bdc0
   srr0 = 0x00206dc4    r1 = 0xbfff58a0
    Found by: previous frame's frame pointer
42  XUL + 0xc70ee4
   srr0 = 0x04283ee8    r1 = 0xbfff5910
    Found by: previous frame's frame pointer
43  XUL + 0x962464
   srr0 = 0x03f75468    r1 = 0xbfff5a00
    Found by: previous frame's frame pointer
44  XUL + 0x962788
   srr0 = 0x03f7578c    r1 = 0xbfff5b00
    Found by: previous frame's frame pointer
45  XUL + 0x96282c
   srr0 = 0x03f75830    r1 = 0xbfff5bf0
    Found by: previous frame's frame pointer
46  XUL + 0x962c64
   srr0 = 0x03f75c68    r1 = 0xbfff5c60
    Found by: previous frame's frame pointer
47  XUL + 0x1ee04c
   srr0 = 0x03801050    r1 = 0xbfff5cc0
    Found by: previous frame's frame pointer
48  XUL + 0x1ecccc
   srr0 = 0x037ffcd0    r1 = 0xbfff5d30
    Found by: previous frame's frame pointer
49  XUL + 0x2da7c4
   srr0 = 0x038ed7c8    r1 = 0xbfff5d80
    Found by: previous frame's frame pointer
50  XUL + 0x1a46cc
   srr0 = 0x037b76d0    r1 = 0xbfff5e00
    Found by: previous frame's frame pointer
51  XUL + 0x1a486c
   srr0 = 0x037b7870    r1 = 0xbfff5e60
    Found by: previous frame's frame pointer
52  XUL + 0x1854838
   srr0 = 0x04e6783c    r1 = 0xbfff5ec0
    Found by: previous frame's frame pointer
53  XUL + 0x1896e38
   srr0 = 0x04ea9e3c    r1 = 0xbfff5f10
    Found by: previous frame's frame pointer
54  XUL + 0x17fb394
   srr0 = 0x04e0e398    r1 = 0xbfff5fb0
    Found by: previous frame's frame pointer
55  XUL + 0x12a3090
   srr0 = 0x048b6094    r1 = 0xbfff6010
    Found by: previous frame's frame pointer
56  XUL + 0x12992dc
   srr0 = 0x048ac2e0    r1 = 0xbfff60d0
    Found by: previous frame's frame pointer
57  XUL + 0x12d4ae0
   srr0 = 0x048e7ae4    r1 = 0xbfff6120
    Found by: previous frame's frame pointer
58  XUL + 0x122b988
   srr0 = 0x0483e98c    r1 = 0xbfff61c0
    Found by: previous frame's frame pointer
59  XUL + 0x122d814
   srr0 = 0x04840818    r1 = 0xbfff6620
    Found by: previous frame's frame pointer
60  XUL + 0xcaa118
   srr0 = 0x042bd11c    r1 = 0xbfff6690
    Found by: previous frame's frame pointer
61  XUL + 0xcab20c
   srr0 = 0x042be210    r1 = 0xbfff6880
    Found by: previous frame's frame pointer
62  XUL + 0x18bed60
   srr0 = 0x04ed1d64    r1 = 0xbfff68f0
    Found by: previous frame's frame pointer
63  XUL + 0x18be414
   srr0 = 0x04ed1418    r1 = 0xbfff69b0
    Found by: previous frame's frame pointer
64  XUL + 0xf36fc
   srr0 = 0x03706700    r1 = 0xbfff6a00
    Found by: previous frame's frame pointer
65  XUL + 0x102c90
   srr0 = 0x03715c94    r1 = 0xbfff6dc0
    Found by: previous frame's frame pointer
66  libmozjs.dylib + 0xb1f0c
   srr0 = 0x0029cf10    r1 = 0xbfff6ec0
    Found by: previous frame's frame pointer
67  libmozjs.dylib + 0x9d0c8
   srr0 = 0x002880cc    r1 = 0xbfff6fd0
    Found by: previous frame's frame pointer
68  libmozjs.dylib + 0xb022c
   srr0 = 0x0029b230    r1 = 0xbfff7c30
    Found by: previous frame's frame pointer
69  libmozjs.dylib + 0xd7db0
   srr0 = 0x002c2db4    r1 = 0xbfff7d00
    Found by: previous frame's frame pointer
70  libmozjs.dylib + 0xb1f0c
   srr0 = 0x0029cf10    r1 = 0xbfff7e20
    Found by: previous frame's frame pointer
71  libmozjs.dylib + 0x9d0c8
   srr0 = 0x002880cc    r1 = 0xbfff7f30
    Found by: previous frame's frame pointer
72  libmozjs.dylib + 0xb022c
   srr0 = 0x0029b230    r1 = 0xbfff8b90
    Found by: previous frame's frame pointer
73  libmozjs.dylib + 0x1bdc0
   srr0 = 0x00206dc4    r1 = 0xbfff8c60
    Found by: previous frame's frame pointer
74  XUL + 0xc70ee4
   srr0 = 0x04283ee8    r1 = 0xbfff8cd0
    Found by: previous frame's frame pointer
75  XUL + 0x962464
   srr0 = 0x03f75468    r1 = 0xbfff8dc0
    Found by: previous frame's frame pointer
76  XUL + 0x962788
   srr0 = 0x03f7578c    r1 = 0xbfff8ec0
    Found by: previous frame's frame pointer
77  XUL + 0x96282c
   srr0 = 0x03f75830    r1 = 0xbfff8fb0
    Found by: previous frame's frame pointer
78  XUL + 0x962c64
   srr0 = 0x03f75c68    r1 = 0xbfff9020
    Found by: previous frame's frame pointer
79  XUL + 0x1ee04c
   srr0 = 0x03801050    r1 = 0xbfff9080
    Found by: previous frame's frame pointer
80  XUL + 0x1ecccc
   srr0 = 0x037ffcd0    r1 = 0xbfff90f0
    Found by: previous frame's frame pointer
81  XUL + 0x2da7c4
   srr0 = 0x038ed7c8    r1 = 0xbfff9140
    Found by: previous frame's frame pointer
82  XUL + 0x1a46cc
   srr0 = 0x037b76d0    r1 = 0xbfff91c0
    Found by: previous frame's frame pointer
83  XUL + 0x1a486c
   srr0 = 0x037b7870    r1 = 0xbfff9220
    Found by: previous frame's frame pointer
84  XUL + 0x1854838
   srr0 = 0x04e6783c    r1 = 0xbfff9280
    Found by: previous frame's frame pointer
85  XUL + 0x1896e38
   srr0 = 0x04ea9e3c    r1 = 0xbfff92d0
    Found by: previous frame's frame pointer
86  XUL + 0x17fb5b0
   srr0 = 0x04e0e5b4    r1 = 0xbfff9370
    Found by: previous frame's frame pointer
87  XUL + 0x1673660
   srr0 = 0x04c86664    r1 = 0xbfff93d0
    Found by: previous frame's frame pointer
88  XUL + 0x1619810
   srr0 = 0x04c2c814    r1 = 0xbfff9430
    Found by: previous frame's frame pointer
89  CoreFoundation + 0x690d0
   srr0 = 0x9776f0d4    r1 = 0xbfff9800
    Found by: previous frame's frame pointer
90  HIToolbox + 0x30b14
   srr0 = 0x907b8b18    r1 = 0xbfffa040
    Found by: previous frame's frame pointer
91  HIToolbox + 0x30938
   srr0 = 0x907b893c    r1 = 0xbfffa0a0
    Found by: previous frame's frame pointer
92  HIToolbox + 0x30778
   srr0 = 0x907b877c    r1 = 0xbfffa120
    Found by: previous frame's frame pointer
93  AppKit + 0x3c244
   srr0 = 0x94305248    r1 = 0xbfffa170
    Found by: previous frame's frame pointer
94  AppKit + 0x3bbfc
   srr0 = 0x94304c00    r1 = 0xbfffa540
    Found by: previous frame's frame pointer
95  AppKit + 0x3589c
   srr0 = 0x942fe8a0    r1 = 0xbfffa830
    Found by: previous frame's frame pointer
96  XUL + 0x1617028
   srr0 = 0x04c2a02c    r1 = 0xbfffabf0
    Found by: previous frame's frame pointer
97  XUL + 0x12d4348
   srr0 = 0x048e734c    r1 = 0xbfffaf70
    Found by: previous frame's frame pointer
98  XUL + 0x16c80
   srr0 = 0x03629c84    r1 = 0xbfffafd0
    Found by: previous frame's frame pointer
99  firefox-bin + 0x22cc
   srr0 = 0x000032d0    r1 = 0xbfffb510
    Found by: previous frame's frame pointer
100  firefox-bin + 0xd84
   srr0 = 0x00001d88    r1 = 0xbfffb5a0
    Found by: previous frame's frame pointer
101  firefox-bin + 0xa88
   srr0 = 0x00001a8c    r1 = 0xbfffb620
    Found by: previous frame's frame pointer

Thread 1
 0  libSystem.B.dylib + 0x1258
   srr0 = 0x93051258    r1 = 0xf0102c80
    Found by: given as instruction pointer in context
 1  libnspr4.dylib + 0x2f11c
   srr0 = 0x000a3120    r1 = 0xf0102d10
    Found by: previous frame's frame pointer
 2  libnspr4.dylib + 0x2f7d8
   srr0 = 0x000a37dc    r1 = 0xf0102d80
    Found by: previous frame's frame pointer
 3  XUL + 0xcd048
   srr0 = 0x036e004c    r1 = 0xf0102de0
    Found by: previous frame's frame pointer
 4  libnspr4.dylib + 0x39844
   srr0 = 0x000ad848    r1 = 0xf0102e40
    Found by: previous frame's frame pointer
 5  libSystem.B.dylib + 0x430d0
   srr0 = 0x930930d4    r1 = 0xf0102ea0
    Found by: previous frame's frame pointer

Thread 2
 0  libSystem.B.dylib + 0x4a094
   srr0 = 0x9309a094    r1 = 0xf01844c0
    Found by: given as instruction pointer in context
 1  libnspr4.dylib + 0x3e078
   srr0 = 0x000b207c    r1 = 0xf0184520
    Found by: previous frame's frame pointer
 2  libnspr4.dylib + 0x3738c
   srr0 = 0x000ab390    r1 = 0xf0184720
    Found by: previous frame's frame pointer
 3  libnspr4.dylib + 0x377b0
   srr0 = 0x000ab7b4    r1 = 0xf01849b0
    Found by: previous frame's frame pointer
 4  XUL + 0x1e6e04
   srr0 = 0x037f9e08    r1 = 0xf0184a00
    Found by: previous frame's frame pointer
 5  XUL + 0x1e8c08
   srr0 = 0x037fbc0c    r1 = 0xf0184a70
    Found by: previous frame's frame pointer
 6  XUL + 0x1e9018
   srr0 = 0x037fc01c    r1 = 0xf0184b00
    Found by: previous frame's frame pointer
 7  XUL + 0x1896cc8
   srr0 = 0x04ea9ccc    r1 = 0xf0184b60
    Found by: previous frame's frame pointer
 8  XUL + 0x17fb394
   srr0 = 0x04e0e398    r1 = 0xf0184c00
    Found by: previous frame's frame pointer
 9  XUL + 0x1e867c
   srr0 = 0x037fb680    r1 = 0xf0184c60
    Found by: previous frame's frame pointer
10  XUL + 0x1896e38
   srr0 = 0x04ea9e3c    r1 = 0xf0184cd0
    Found by: previous frame's frame pointer
11  XUL + 0x17fb394
   srr0 = 0x04e0e398    r1 = 0xf0184d70
    Found by: previous frame's frame pointer
12  XUL + 0x18970e8
   srr0 = 0x04eaa0ec    r1 = 0xf0184dd0
    Found by: previous frame's frame pointer
13  libnspr4.dylib + 0x39844
   srr0 = 0x000ad848    r1 = 0xf0184e40
    Found by: previous frame's frame pointer
14  libSystem.B.dylib + 0x430d0
   srr0 = 0x930930d4    r1 = 0xf0184ea0
    Found by: previous frame's frame pointer

Thread 3
 0  libSystem.B.dylib + 0x1258
   srr0 = 0x93051258    r1 = 0xf0206ae0
    Found by: given as instruction pointer in context
 1  libnspr4.dylib + 0x2f11c
   srr0 = 0x000a3120    r1 = 0xf0206b70
    Found by: previous frame's frame pointer
 2  libnspr4.dylib + 0x2f7d8
   srr0 = 0x000a37dc    r1 = 0xf0206be0
    Found by: previous frame's frame pointer
 3  XUL + 0x18a3b58
   srr0 = 0x04eb6b5c    r1 = 0xf0206c40
    Found by: previous frame's frame pointer
 4  XUL + 0x1896e38
   srr0 = 0x04ea9e3c    r1 = 0xf0206cd0
    Found by: previous frame's frame pointer
 5  XUL + 0x17fb394
   srr0 = 0x04e0e398    r1 = 0xf0206d70
    Found by: previous frame's frame pointer
 6  XUL + 0x18970e8
   srr0 = 0x04eaa0ec    r1 = 0xf0206dd0
    Found by: previous frame's frame pointer
 7  libnspr4.dylib + 0x39844
   srr0 = 0x000ad848    r1 = 0xf0206e40
    Found by: previous frame's frame pointer
 8  libSystem.B.dylib + 0x430d0
   srr0 = 0x930930d4    r1 = 0xf0206ea0
    Found by: previous frame's frame pointer

Thread 4
 0  libSystem.B.dylib + 0x1258
   srr0 = 0x93051258    r1 = 0xf0288a10
    Found by: given as instruction pointer in context
 1  libnspr4.dylib + 0x2f11c
   srr0 = 0x000a3120    r1 = 0xf0288aa0
    Found by: previous frame's frame pointer
 2  libnspr4.dylib + 0x2f7d8
   srr0 = 0x000a37dc    r1 = 0xf0288b10
    Found by: previous frame's frame pointer
 3  libnspr4.dylib + 0x3014c
   srr0 = 0x000a4150    r1 = 0xf0288b70
    Found by: previous frame's frame pointer
 4  XUL + 0x2abbb8
   srr0 = 0x038bebbc    r1 = 0xf0288bd0
    Found by: previous frame's frame pointer
 5  XUL + 0x189d970
   srr0 = 0x04eb0974    r1 = 0xf0288c20
    Found by: previous frame's frame pointer
 6  XUL + 0x1896e38
   srr0 = 0x04ea9e3c    r1 = 0xf0288cd0
    Found by: previous frame's frame pointer
 7  XUL + 0x17fb394
   srr0 = 0x04e0e398    r1 = 0xf0288d70
    Found by: previous frame's frame pointer
 8  XUL + 0x18970e8
   srr0 = 0x04eaa0ec    r1 = 0xf0288dd0
    Found by: previous frame's frame pointer
 9  libnspr4.dylib + 0x39844
   srr0 = 0x000ad848    r1 = 0xf0288e40
    Found by: previous frame's frame pointer
10  libSystem.B.dylib + 0x430d0
   srr0 = 0x930930d4    r1 = 0xf0288ea0
    Found by: previous frame's frame pointer

Thread 5
 0  libSystem.B.dylib + 0x1238
   srr0 = 0x93051238    r1 = 0xf030aa70
    Found by: given as instruction pointer in context
 1  libnspr4.dylib + 0x2f7ac
   srr0 = 0x000a37b0    r1 = 0xf030ab00
    Found by: previous frame's frame pointer
 2  libnspr4.dylib + 0x3014c
   srr0 = 0x000a4150    r1 = 0xf030ab60
    Found by: previous frame's frame pointer
 3  XUL + 0x2abbb8
   srr0 = 0x038bebbc    r1 = 0xf030abc0
    Found by: previous frame's frame pointer
 4  XUL + 0x1894200
   srr0 = 0x04ea7204    r1 = 0xf030ac10
    Found by: previous frame's frame pointer
 5  XUL + 0x1897f40
   srr0 = 0x04eaaf44    r1 = 0xf030ac80
    Found by: previous frame's frame pointer
 6  XUL + 0x1896d4c
   srr0 = 0x04ea9d50    r1 = 0xf030acd0
    Found by: previous frame's frame pointer
 7  XUL + 0x17fb394
   srr0 = 0x04e0e398    r1 = 0xf030ad70
    Found by: previous frame's frame pointer
 8  XUL + 0x18970e8
   srr0 = 0x04eaa0ec    r1 = 0xf030add0
    Found by: previous frame's frame pointer
 9  libnspr4.dylib + 0x39844
   srr0 = 0x000ad848    r1 = 0xf030ae40
    Found by: previous frame's frame pointer
10  libSystem.B.dylib + 0x430d0
   srr0 = 0x930930d4    r1 = 0xf030aea0
    Found by: previous frame's frame pointer

Thread 6
 0  libSystem.B.dylib + 0x1258
   srr0 = 0x93051258    r1 = 0xf038cbf0
    Found by: given as instruction pointer in context
 1  libnspr4.dylib + 0x2f11c
   srr0 = 0x000a3120    r1 = 0xf038cc80
    Found by: previous frame's frame pointer
 2  libnspr4.dylib + 0x2f7d8
   srr0 = 0x000a37dc    r1 = 0xf038ccf0
    Found by: previous frame's frame pointer
 3  XUL + 0x2072f0
   srr0 = 0x0381a2f4    r1 = 0xf038cd50
    Found by: previous frame's frame pointer
 4  XUL + 0x207514
   srr0 = 0x0381a518    r1 = 0xf038cdd0
    Found by: previous frame's frame pointer
 5  libnspr4.dylib + 0x39844
   srr0 = 0x000ad848    r1 = 0xf038ce40
    Found by: previous frame's frame pointer
 6  libSystem.B.dylib + 0x430d0
   srr0 = 0x930930d4    r1 = 0xf038cea0
    Found by: previous frame's frame pointer

Thread 7
 0  libSystem.B.dylib + 0x1238
   srr0 = 0x93051238    r1 = 0xf040de30
    Found by: given as instruction pointer in context
 1  libnspr4.dylib + 0x2f7ac
   srr0 = 0x000a37b0    r1 = 0xf040dec0
    Found by: previous frame's frame pointer
 2  libnspr4.dylib + 0x3014c
   srr0 = 0x000a4150    r1 = 0xf040df20
    Found by: previous frame's frame pointer
 3  XUL + 0x2abbb8
   srr0 = 0x038bebbc    r1 = 0xf040df80
    Found by: previous frame's frame pointer
 4  XUL + 0x1894200
   srr0 = 0x04ea7204    r1 = 0xf040dfd0
    Found by: previous frame's frame pointer
 5  XUL + 0x1897f40
   srr0 = 0x04eaaf44    r1 = 0xf040e040
    Found by: previous frame's frame pointer
 6  XUL + 0x1896d4c
   srr0 = 0x04ea9d50    r1 = 0xf040e090
    Found by: previous frame's frame pointer
 7  XUL + 0x17fb394
   srr0 = 0x04e0e398    r1 = 0xf040e130
    Found by: previous frame's frame pointer
 8  XUL + 0x18a8198
   srr0 = 0x04ebb19c    r1 = 0xf040e190
    Found by: previous frame's frame pointer
 9  XUL + 0x18bea10
   srr0 = 0x04ed1a14    r1 = 0xf040e210
    Found by: previous frame's frame pointer
10  XUL + 0x18bf5a0
   srr0 = 0x04ed25a4    r1 = 0xf040e340
    Found by: previous frame's frame pointer
11  XUL + 0x136261c
   srr0 = 0x04975620    r1 = 0xf040e3f0
    Found by: previous frame's frame pointer
12  XUL + 0x136293c
   srr0 = 0x04975940    r1 = 0xf040e4b0
    Found by: previous frame's frame pointer
13  XUL + 0x13429c4
   srr0 = 0x049559c8    r1 = 0xf040e510
    Found by: previous frame's frame pointer
14  libssl3.dylib + 0x19bbc
   srr0 = 0x004c5bc0    r1 = 0xf040e860
    Found by: previous frame's frame pointer
15  libssl3.dylib + 0x1a388
   srr0 = 0x004c638c    r1 = 0xf040e8e0
    Found by: previous frame's frame pointer
16  libssl3.dylib + 0x1a618
   srr0 = 0x004c661c    r1 = 0xf040e980
    Found by: previous frame's frame pointer
17  libssl3.dylib + 0x1b354
   srr0 = 0x004c7358    r1 = 0xf040e9f0
    Found by: previous frame's frame pointer
18  libssl3.dylib + 0x1ca04
   srr0 = 0x004c8a08    r1 = 0xf040eae0
    Found by: previous frame's frame pointer
19  libssl3.dylib + 0x20878
   srr0 = 0x004cc87c    r1 = 0xf040eb60
    Found by: previous frame's frame pointer
20  libssl3.dylib + 0x2ebd8
   srr0 = 0x004dabdc    r1 = 0xf040ebc0
    Found by: previous frame's frame pointer
21  libssl3.dylib + 0x31824
   srr0 = 0x004dd828    r1 = 0xf040ec20
    Found by: previous frame's frame pointer
22  libssl3.dylib + 0x31a34
   srr0 = 0x004dda38    r1 = 0xf040ec80
    Found by: previous frame's frame pointer
23  libssl3.dylib + 0x3b4d0
   srr0 = 0x004e74d4    r1 = 0xf040ecd0
    Found by: previous frame's frame pointer
24  XUL + 0x13396a4
   srr0 = 0x0494c6a8    r1 = 0xf040ed30
    Found by: previous frame's frame pointer
25  XUL + 0x1336ef4
   srr0 = 0x04949ef8    r1 = 0xf040ede0
    Found by: previous frame's frame pointer
26  libnspr4.dylib + 0x39844
   srr0 = 0x000ad848    r1 = 0xf040ee40
    Found by: previous frame's frame pointer
27  libSystem.B.dylib + 0x430d0
   srr0 = 0x930930d4    r1 = 0xf040eea0
    Found by: previous frame's frame pointer

Thread 8
 0  libSystem.B.dylib + 0x1238
   srr0 = 0x93051238    r1 = 0xf0490c70
    Found by: given as instruction pointer in context
 1  libnspr4.dylib + 0x2f7ac
   srr0 = 0x000a37b0    r1 = 0xf0490d00
    Found by: previous frame's frame pointer
 2  XUL + 0x133a3f4
   srr0 = 0x0494d3f8    r1 = 0xf0490d60
    Found by: previous frame's frame pointer
 3  XUL + 0x1336ef4
   srr0 = 0x04949ef8    r1 = 0xf0490de0
    Found by: previous frame's frame pointer
 4  libnspr4.dylib + 0x39844
   srr0 = 0x000ad848    r1 = 0xf0490e40
    Found by: previous frame's frame pointer
 5  libSystem.B.dylib + 0x430d0
   srr0 = 0x930930d4    r1 = 0xf0490ea0
    Found by: previous frame's frame pointer

Thread 9
 0  libSystem.B.dylib + 0x1238
   srr0 = 0x93051238    r1 = 0xf0512a70
    Found by: given as instruction pointer in context
 1  libnspr4.dylib + 0x2f7ac
   srr0 = 0x000a37b0    r1 = 0xf0512b00
    Found by: previous frame's frame pointer
 2  libnspr4.dylib + 0x3014c
   srr0 = 0x000a4150    r1 = 0xf0512b60
    Found by: previous frame's frame pointer
 3  XUL + 0x2abbb8
   srr0 = 0x038bebbc    r1 = 0xf0512bc0
    Found by: previous frame's frame pointer
 4  XUL + 0x1894200
   srr0 = 0x04ea7204    r1 = 0xf0512c10
    Found by: previous frame's frame pointer
 5  XUL + 0x1897f40
   srr0 = 0x04eaaf44    r1 = 0xf0512c80
    Found by: previous frame's frame pointer
 6  XUL + 0x1896d4c
   srr0 = 0x04ea9d50    r1 = 0xf0512cd0
    Found by: previous frame's frame pointer
 7  XUL + 0x17fb394
   srr0 = 0x04e0e398    r1 = 0xf0512d70
    Found by: previous frame's frame pointer
 8  XUL + 0x18970e8
   srr0 = 0x04eaa0ec    r1 = 0xf0512dd0
    Found by: previous frame's frame pointer
 9  libnspr4.dylib + 0x39844
   srr0 = 0x000ad848    r1 = 0xf0512e40
    Found by: previous frame's frame pointer
10  libSystem.B.dylib + 0x430d0
   srr0 = 0x930930d4    r1 = 0xf0512ea0
    Found by: previous frame's frame pointer

Thread 10
 0  libSystem.B.dylib + 0x1258
   srr0 = 0x93051258    r1 = 0xf0616bf0
    Found by: given as instruction pointer in context
 1  libnspr4.dylib + 0x2f11c
   srr0 = 0x000a3120    r1 = 0xf0616c80
    Found by: previous frame's frame pointer
 2  libnspr4.dylib + 0x2f7d8
   srr0 = 0x000a37dc    r1 = 0xf0616cf0
    Found by: previous frame's frame pointer
 3  XUL + 0x2072f0
   srr0 = 0x0381a2f4    r1 = 0xf0616d50
    Found by: previous frame's frame pointer
 4  XUL + 0x207514
   srr0 = 0x0381a518    r1 = 0xf0616dd0
    Found by: previous frame's frame pointer
 5  libnspr4.dylib + 0x39844
   srr0 = 0x000ad848    r1 = 0xf0616e40
    Found by: previous frame's frame pointer
 6  libSystem.B.dylib + 0x430d0
   srr0 = 0x930930d4    r1 = 0xf0616ea0
    Found by: previous frame's frame pointer

Thread 11
 0  libSystem.B.dylib + 0x1258
   srr0 = 0x93051258    r1 = 0xf0698bf0
    Found by: given as instruction pointer in context
 1  libnspr4.dylib + 0x2f11c
   srr0 = 0x000a3120    r1 = 0xf0698c80
    Found by: previous frame's frame pointer
 2  libnspr4.dylib + 0x2f7d8
   srr0 = 0x000a37dc    r1 = 0xf0698cf0
    Found by: previous frame's frame pointer
 3  XUL + 0x2072f0
   srr0 = 0x0381a2f4    r1 = 0xf0698d50
    Found by: previous frame's frame pointer
 4  XUL + 0x207514
   srr0 = 0x0381a518    r1 = 0xf0698dd0
    Found by: previous frame's frame pointer
 5  libnspr4.dylib + 0x39844
   srr0 = 0x000ad848    r1 = 0xf0698e40
    Found by: previous frame's frame pointer
 6  libSystem.B.dylib + 0x430d0
   srr0 = 0x930930d4    r1 = 0xf0698ea0
    Found by: previous frame's frame pointer

Thread 12
 0  libSystem.B.dylib + 0x1258
   srr0 = 0x93051258    r1 = 0xf071abf0
    Found by: given as instruction pointer in context
 1  libnspr4.dylib + 0x2f11c
   srr0 = 0x000a3120    r1 = 0xf071ac80
    Found by: previous frame's frame pointer
 2  libnspr4.dylib + 0x2f7d8
   srr0 = 0x000a37dc    r1 = 0xf071acf0
    Found by: previous frame's frame pointer
 3  XUL + 0x2072f0
   srr0 = 0x0381a2f4    r1 = 0xf071ad50
    Found by: previous frame's frame pointer
 4  XUL + 0x207514
   srr0 = 0x0381a518    r1 = 0xf071add0
    Found by: previous frame's frame pointer
 5  libnspr4.dylib + 0x39844
   srr0 = 0x000ad848    r1 = 0xf071ae40
    Found by: previous frame's frame pointer
 6  libSystem.B.dylib + 0x430d0
   srr0 = 0x930930d4    r1 = 0xf071aea0
    Found by: previous frame's frame pointer

Thread 13
 0  libSystem.B.dylib + 0x1258
   srr0 = 0x93051258    r1 = 0xf079cbf0
    Found by: given as instruction pointer in context
 1  libnspr4.dylib + 0x2f11c
   srr0 = 0x000a3120    r1 = 0xf079cc80
    Found by: previous frame's frame pointer
 2  libnspr4.dylib + 0x2f7d8
   srr0 = 0x000a37dc    r1 = 0xf079ccf0
    Found by: previous frame's frame pointer
 3  XUL + 0x2072f0
   srr0 = 0x0381a2f4    r1 = 0xf079cd50
    Found by: previous frame's frame pointer
 4  XUL + 0x207514
   srr0 = 0x0381a518    r1 = 0xf079cdd0
    Found by: previous frame's frame pointer
 5  libnspr4.dylib + 0x39844
   srr0 = 0x000ad848    r1 = 0xf079ce40
    Found by: previous frame's frame pointer
 6  libSystem.B.dylib + 0x430d0
   srr0 = 0x930930d4    r1 = 0xf079cea0
    Found by: previous frame's frame pointer

Thread 14
 0  libSystem.B.dylib + 0x1258
   srr0 = 0x93051258    r1 = 0xf081ebf0
    Found by: given as instruction pointer in context
 1  libnspr4.dylib + 0x2f11c
   srr0 = 0x000a3120    r1 = 0xf081ec80
    Found by: previous frame's frame pointer
 2  libnspr4.dylib + 0x2f7d8
   srr0 = 0x000a37dc    r1 = 0xf081ecf0
    Found by: previous frame's frame pointer
 3  XUL + 0x2072f0
   srr0 = 0x0381a2f4    r1 = 0xf081ed50
    Found by: previous frame's frame pointer
 4  XUL + 0x207514
   srr0 = 0x0381a518    r1 = 0xf081edd0
    Found by: previous frame's frame pointer
 5  libnspr4.dylib + 0x39844
   srr0 = 0x000ad848    r1 = 0xf081ee40
    Found by: previous frame's frame pointer
 6  libSystem.B.dylib + 0x430d0
   srr0 = 0x930930d4    r1 = 0xf081eea0
    Found by: previous frame's frame pointer

Thread 15
 0  libSystem.B.dylib + 0x1258
   srr0 = 0x93051258    r1 = 0xf08a0bf0
    Found by: given as instruction pointer in context
 1  libnspr4.dylib + 0x2f11c
   srr0 = 0x000a3120    r1 = 0xf08a0c80
    Found by: previous frame's frame pointer
 2  libnspr4.dylib + 0x2f7d8
   srr0 = 0x000a37dc    r1 = 0xf08a0cf0
    Found by: previous frame's frame pointer
 3  XUL + 0x2072f0
   srr0 = 0x0381a2f4    r1 = 0xf08a0d50
    Found by: previous frame's frame pointer
 4  XUL + 0x207514
   srr0 = 0x0381a518    r1 = 0xf08a0dd0
    Found by: previous frame's frame pointer
 5  libnspr4.dylib + 0x39844
   srr0 = 0x000ad848    r1 = 0xf08a0e40
    Found by: previous frame's frame pointer
 6  libSystem.B.dylib + 0x430d0
   srr0 = 0x930930d4    r1 = 0xf08a0ea0
    Found by: previous frame's frame pointer

Thread 16
 0  libSystem.B.dylib + 0x1238
   srr0 = 0x93051238    r1 = 0xf0922920
    Found by: given as instruction pointer in context
 1  FlashPlayer-10.4-10.5 + 0x3b8284
   srr0 = 0x138b8288    r1 = 0xf09229b0
    Found by: previous frame's frame pointer
 2  FlashPlayer-10.4-10.5 + 0x19014
   srr0 = 0x13519018    r1 = 0xf0922a20
    Found by: previous frame's frame pointer
 3  FlashPlayer-10.4-10.5 + 0x3b8384
   srr0 = 0x138b8388    r1 = 0xf0922a80
    Found by: previous frame's frame pointer
 4  FlashPlayer-10.4-10.5 + 0x3b83d0
   srr0 = 0x138b83d4    r1 = 0xf0922df0
    Found by: previous frame's frame pointer
 5  FlashPlayer-10.4-10.5 + 0x3b8518
   srr0 = 0x138b851c    r1 = 0xf0922e50
    Found by: previous frame's frame pointer
 6  libSystem.B.dylib + 0x430d0
   srr0 = 0x930930d4    r1 = 0xf0922ea0
    Found by: previous frame's frame pointer

Thread 17
 0  libSystem.B.dylib + 0x1238
   srr0 = 0x93051238    r1 = 0xf09a4920
    Found by: given as instruction pointer in context
 1  FlashPlayer-10.4-10.5 + 0x3b8284
   srr0 = 0x138b8288    r1 = 0xf09a49b0
    Found by: previous frame's frame pointer
 2  FlashPlayer-10.4-10.5 + 0x19014
   srr0 = 0x13519018    r1 = 0xf09a4a20
    Found by: previous frame's frame pointer
 3  FlashPlayer-10.4-10.5 + 0x3b8384
   srr0 = 0x138b8388    r1 = 0xf09a4a80
    Found by: previous frame's frame pointer
 4  FlashPlayer-10.4-10.5 + 0x3b83d0
   srr0 = 0x138b83d4    r1 = 0xf09a4df0
    Found by: previous frame's frame pointer
 5  FlashPlayer-10.4-10.5 + 0x3b8518
   srr0 = 0x138b851c    r1 = 0xf09a4e50
    Found by: previous frame's frame pointer
 6  libSystem.B.dylib + 0x430d0
   srr0 = 0x930930d4    r1 = 0xf09a4ea0
    Found by: previous frame's frame pointer

Thread 18
 0  libSystem.B.dylib + 0x11d8
   srr0 = 0x930511d8    r1 = 0xf0a26540
    Found by: given as instruction pointer in context
 1  CoreFoundation + 0x69394
   srr0 = 0x9776f398    r1 = 0xf0a265b0
    Found by: previous frame's frame pointer
 2  CoreAudio + 0x21fa8
   srr0 = 0x93f41fac    r1 = 0xf0a26df0
    Found by: previous frame's frame pointer
 3  CoreAudio + 0x21de4
   srr0 = 0x93f41de8    r1 = 0xf0a26e50
    Found by: previous frame's frame pointer
 4  libSystem.B.dylib + 0x430d0
   srr0 = 0x930930d4    r1 = 0xf0a26ea0
    Found by: previous frame's frame pointer

Thread 19
 0  libSystem.B.dylib + 0x11d8
   srr0 = 0x930511d8    r1 = 0xf0aa8510
    Found by: given as instruction pointer in context
 1  CoreFoundation + 0x69394
   srr0 = 0x9776f398    r1 = 0xf0aa8580
    Found by: previous frame's frame pointer
 2  CoreFoundation + 0x69c1c
   srr0 = 0x9776fc20    r1 = 0xf0aa8dc0
    Found by: previous frame's frame pointer
 3  QuickTime + 0x27133c
   srr0 = 0x009c8340    r1 = 0xf0aa8e20
    Found by: previous frame's frame pointer
 4  libSystem.B.dylib + 0x430d0
   srr0 = 0x930930d4    r1 = 0xf0aa8ea0
    Found by: previous frame's frame pointer

Thread 20
 0  libSystem.B.dylib + 0x1258
   srr0 = 0x93051258    r1 = 0xf0b2abc0
    Found by: given as instruction pointer in context
 1  CoreAudio + 0x33780
   srr0 = 0x93f53784    r1 = 0xf0b2ac50
    Found by: previous frame's frame pointer
 2  CoreAudio + 0x339f0
   srr0 = 0x93f539f4    r1 = 0xf0b2acb0
    Found by: previous frame's frame pointer
 3  CoreAudio + 0x337f0
   srr0 = 0x93f537f4    r1 = 0xf0b2ae00
    Found by: previous frame's frame pointer
 4  CoreAudio + 0x21de4
   srr0 = 0x93f41de8    r1 = 0xf0b2ae50
    Found by: previous frame's frame pointer
 5  libSystem.B.dylib + 0x430d0
   srr0 = 0x930930d4    r1 = 0xf0b2aea0
    Found by: previous frame's frame pointer

Loaded modules:
0x00001000 - 0x00005fff  firefox-bin  ???  (main)
0x0000c000 - 0x0000efff  ExceptionHandling  ???
0x00014000 - 0x00016fff  libxpcom.dylib  ???
0x0001b000 - 0x00026fff  libplds4.dylib  ???
0x0002e000 - 0x0003afff  libplc4.dylib  ???
0x00074000 - 0x000c4fff  libnspr4.dylib  ???
0x000e8000 - 0x00107fff  CoreVideo  ???
0x0011c000 - 0x0014efff  libsmime3.dylib  ???
0x001eb000 - 0x00377fff  libmozjs.dylib  ???
0x003d6000 - 0x0047efff  libsqlite3.dylib  ???
0x004ac000 - 0x004fdfff  libssl3.dylib  ???
0x00519000 - 0x00696fff  libnss3.dylib  ???
0x00722000 - 0x00741fff  libnssutil3.dylib  ???
0x00757000 - 0x00a8efff  QuickTime  ???
0x00e33000 - 0x00e5bfff  libalerts_s.dylib  ???
0x00e7f000 - 0x00f05fff  libbrowsercomps.dylib  ???
0x00f6e000 - 0x00f8afff  libbrowserdirprovider.dylib  ???
0x00fa7000 - 0x00faffff  libMyService.dylib  ???
0x00fbb000 - 0x00fc3fff  libtestdynamic.dylib  ???
0x00fcf000 - 0x00fdefff  libxpcomsample.dylib  ???
0x01b00000 - 0x01b34fff  PrintCocoaUI  ???
0x01b60000 - 0x01b6ffff  libSimplifiedChineseConverter.dylib  ???
0x01cc7000 - 0x01cc9fff  Unicode Encodings  ???
0x03613000 - 0x0532ffff  XUL  ???
0x0d687000 - 0x0d68bfff  Flash Player  ???
0x0d691000 - 0x0d6cffff  QuickTimeFireWireDV  ???
0x0f8af000 - 0x0fa96fff  RawCamera  ???
0x100bb000 - 0x1010cfff  libsoftokn3.dylib  ???
0x10129000 - 0x10162fff  libnssdbm3.dylib  ???
0x10222000 - 0x102b4fff  libfreebl3.dylib  ???
0x102cb000 - 0x10325fff  libnssckbi.dylib  ???
0x111af000 - 0x111e1fff  QuickTime Plugin  ???
0x11383000 - 0x114c8fff  QTKit  ???
0x115af000 - 0x115edfff  CoreMedia  ???
0x11605000 - 0x11770fff  MediaToolbox  ???
0x12000000 - 0x12203fff  VideoToolbox  ???
0x12256000 - 0x122a5fff  CoreMediaIOServices  ???
0x122d2000 - 0x12e40fff  QuickTimeComponents  ???
0x1304c000 - 0x1320efff  CoreAUC  ???
0x133ac000 - 0x133b6fff  IOFWDVComponents  ???
0x133c0000 - 0x133effff  QuickTimeIIDCDigitizer  ???
0x13500000 - 0x13cf0fff  FlashPlayer-10.4-10.5  ???
0x141ea000 - 0x1423cfff  QuickTimeUSBVDCDigitizer  ???
0x1424a000 - 0x1424efff  AudioIPCPlugIn  ???
0x14253000 - 0x142f5fff  QuickTimeImporters  ???
0x1431b000 - 0x1448bfff  QuickTimeStreaming  ???
0x144fa000 - 0x144fdfff  PDFImporter  ???
0x14502000 - 0x1452dfff  SoundManagerComponents  ???
0x70000000 - 0x700cdfff  CoreAudio  ???
0x90003000 - 0x9004dfff  QuickLookUI  ???
0x90054000 - 0x9019bfff  AudioToolbox  ???
0x9019c000 - 0x9022bfff  DesktopServicesPriv  ???
0x9022c000 - 0x90230fff  libGIF.dylib  ???
0x90231000 - 0x9026efff  libRIP.A.dylib  ???
0x9026f000 - 0x902b1fff  QuartzFilters  ???
0x902c0000 - 0x902c0fff  Carbon  ???
0x902c1000 - 0x902c4fff  Help  ???
0x902c5000 - 0x9034afff  libsqlite3.0.dylib  ???
0x9034b000 - 0x90354fff  DiskArbitration  ???
0x90355000 - 0x9038afff  LDAP  ???
0x9038b000 - 0x9039afff  DSObjCWrappers  ???
0x9039b000 - 0x903c2fff  libcups.2.dylib  ???
0x903c3000 - 0x903cbfff  libbsm.dylib  ???
0x9058f000 - 0x906a3fff  vImage  ???
0x906a4000 - 0x90787fff  libobjc.A.dylib  ???
0x90788000 - 0x90ac1fff  HIToolbox  ???
0x91724000 - 0x91743fff  vecLib  ???
0x91744000 - 0x917f7fff  CFNetwork  ???
0x917f8000 - 0x9187afff  PrintCore  ???
0x9187b000 - 0x91896fff  DirectoryService  ???
0x91897000 - 0x91897fff  CoreServices  ???
0x91898000 - 0x918c1fff  Shortcut  ???
0x91a2e000 - 0x91a49fff  libPng.dylib  ???
0x91c4e000 - 0x91c4ffff  libffi.dylib  ???
0x91c50000 - 0x91c5dfff  libCSync.A.dylib  ???
0x91c62000 - 0x91cc3fff  CoreText  ???
0x91cc4000 - 0x91cccfff  libCGATS.A.dylib  ???
0x91cea000 - 0x91d0bfff  AppleVA  ???
0x91d0c000 - 0x91d2bfff  libresolv.9.dylib  ???
0x91e02000 - 0x923bcfff  libBLAS.dylib  ???
0x923bd000 - 0x925a6fff  Security  ???
0x926f6000 - 0x92790fff  ATS  ???
0x92791000 - 0x9287bfff  libxml2.2.dylib  ???
0x928b2000 - 0x92982fff  ColorSync  ???
0x92983000 - 0x929b8fff  AE  ???
0x929b9000 - 0x929e3fff  libssl.0.9.7.dylib  ???
0x929e4000 - 0x92aacfff  CoreData  ???
0x92acd000 - 0x92acdfff  InstallServer  ???
0x92ace000 - 0x92ad4fff  Backup  ???
0x92ad5000 - 0x92b50fff  SearchKit  ???
0x92b51000 - 0x92b64fff  LangAnalysis  ???
0x92b65000 - 0x92c15fff  Kerberos  ???
0x92d2a000 - 0x92d55fff  libauto.dylib  ???
0x92d96000 - 0x92de5fff  Metadata  ???
0x92de6000 - 0x92f87fff  QuartzComposer  ???
0x92f88000 - 0x93038fff  QD  ???
0x9303f000 - 0x9304ffff  AGL  ???
0x93050000 - 0x931f0fff  libSystem.B.dylib  ???
0x9322f000 - 0x93235fff  DisplayServices  ???
0x9332d000 - 0x938a9fff  CoreGraphics  ???
0x938aa000 - 0x938f9fff  libGLImage.dylib  ???
0x938fa000 - 0x93901fff  CommonPanels  ???
0x93902000 - 0x9398cfff  libvMisc.dylib  ???
0x9398d000 - 0x93ad5fff  libicucore.A.dylib  ???
0x93ad6000 - 0x93af6fff  libJPEG.dylib  ???
0x93af7000 - 0x93b3efff  NavigationServices  ???
0x93b59000 - 0x93b5afff  ApplicationServices  ???
0x93ec4000 - 0x93f05fff  libTIFF.dylib  ???
0x93f06000 - 0x93f1efff  DictionaryServices  ???
0x93f1f000 - 0x93f1ffff  Cocoa  ???
0x93f20000 - 0x93fa8fff  CoreAudio  ???
0x93fa9000 - 0x93fd6fff  libGL.dylib  ???
0x93fd7000 - 0x93fdcfff  libmathCommon.A.dylib  ???
0x93fdd000 - 0x93fddfff  MonitorPanel  ???
0x93fde000 - 0x93fe9fff  HelpData  ???
0x9403a000 - 0x94186fff  ImageIO  ???
0x94187000 - 0x9421cfff  IOKit  ???
0x942c9000 - 0x94a3ffff  AppKit  ???
0x94a40000 - 0x94a5cfff  OpenScripting  ???
0x94a5d000 - 0x94abafff  HIServices  ???
0x94abb000 - 0x94ad9fff  QuickLook  ???
0x94bb1000 - 0x94fdffff  libGLProgrammability.dylib  ???
0x94fe0000 - 0x94fe2fff  libRadiance.dylib  ???
0x94fe3000 - 0x94ff1fff  OpenGL  ???
0x94ff2000 - 0x95089fff  LaunchServices  ???
0x95095000 - 0x950b4fff  vecLib  ???
0x951b0000 - 0x954b2fff  CarbonCore  ???
0x954b3000 - 0x954cafff  ImageCapture  ???
0x954cb000 - 0x9559efff  OSServices  ???
0x9559f000 - 0x9570bfff  AddressBook  ???
0x9570c000 - 0x9571dfff  libsasl2.2.dylib  ???
0x9571e000 - 0x9574ffff  CoreUI  ???
0x95750000 - 0x95753fff  SecurityHI  ???
0x95754000 - 0x9575bfff  Print  ???
0x9575c000 - 0x957e4fff  Ink  ???
0x957fb000 - 0x95823fff  libxslt.1.dylib  ???
0x958d1000 - 0x95bfafff  libLAPACK.dylib  ???
0x95bfb000 - 0x95f60fff  QuartzCore  ???
0x95f61000 - 0x95fc3fff  HTMLRendering  ???
0x96150000 - 0x96189fff  SystemConfiguration  ???
0x9618a000 - 0x961e0fff  libGLU.dylib  ???
0x96284000 - 0x963a9fff  ImageKit  ???
0x96f7e000 - 0x96f8afff  CarbonSound  ???
0x97020000 - 0x9702efff  libz.1.dylib  ???
0x9702f000 - 0x970e9fff  libcrypto.0.9.7.dylib  ???
0x970ea000 - 0x97154fff  PDFKit  ???
0x97155000 - 0x971bcfff  libstdc++.6.dylib  ???
0x9720c000 - 0x9720cfff  AudioUnit  ???
0x97240000 - 0x97253fff  SpeechSynthesis  ???
0x97254000 - 0x973ecfff  JavaScriptCore  ???
0x973ed000 - 0x973edfff  Accelerate  ???
0x973ee000 - 0x97487fff  libvDSP.dylib  ???
0x97705000 - 0x97705fff  Quartz  ???
0x97706000 - 0x9782bfff  CoreFoundation  ???
0x9782c000 - 0x97a72fff  Foundation  ???
0x97a73000 - 0x97a7efff  SpeechRecognition  ???
0x97abe000 - 0x97ac9fff  libgcc_s.1.dylib  ???
0xba900000 - 0xba917fff  libJapaneseConverter.dylib  ???

 EXIT STATUS: NORMAL (0.096221 seconds)
"""]

    for crashreport in crashreport_list:

        crash_data = parse_crashreport(crashreport)
        print "output: " + json.dumps(crash_data, indent=True)


