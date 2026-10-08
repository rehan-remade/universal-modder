// Batch RE helper for headless Ghidra. One JVM load runs many commands.
// Args: <command file> <output file>. Command file lines (# comments):
//   strings <regex>            defined strings matching, with referencing functions
//   funcs <regex>              functions whose name matches
//   decomp <target> [depth]    decompile to out/decomp/<name>_<addr>.c, callees to depth
//   xrefs <target>             callers and callees of a function, refs to an address
//   rename <addr> <name>       name the function at addr (creates one if needed); saved at exit
//   label <addr> <name>        primary label at addr
//   scalar <hex> [max]         instructions with that scalar operand
//   bytes <hex> [max]          byte pattern search in memory (refs listed)
//   dump <addr> <len>          hex dump of memory
//   callers <target> <depth>   caller tree
// target = 0xADDR, ADDR hex, or exact function name.
//@category BannerlordRE
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.scalar.Scalar;
import ghidra.program.model.data.StringDataInstance;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.regex.*;

public class RE extends GhidraScript {
    PrintWriter out;
    DecompInterface dec;
    String decompDir = new File("re_out", "decomp").getPath();   // RE_DECOMP_DIR overrides; keep it OUTSIDE any repository

    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        List<String> lines = Files.readAllLines(Paths.get(a[0]));
        out = new PrintWriter(new FileWriter(a[1]));
        String dd = System.getenv("RE_DECOMP_DIR");
        if (dd != null && !dd.isEmpty()) decompDir = dd;
        new File(decompDir).mkdirs();
        for (String raw : lines) {
            String l = raw.trim();
            if (l.isEmpty() || l.startsWith("#")) continue;
            out.println("=== " + l);
            try { exec(l); } catch (Exception e) { out.println("ERROR " + e); }
            out.flush();
        }
        if (dec != null) dec.dispose();
        out.close();
    }

    void exec(String l) throws Exception {
        String[] p = l.split("\\s+", 3);
        String c = p[0];
        if (c.equals("strings")) strings(l.substring(8).trim());
        else if (c.equals("funcs")) funcs(l.substring(6).trim());
        else if (c.equals("decomp")) decomp(p[1], p.length > 2 ? Integer.parseInt(p[2]) : 0);
        else if (c.equals("xrefs")) xrefs(p[1]);
        else if (c.equals("rename")) rename(p[1], p[2]);
        else if (c.equals("label")) label(p[1], p[2]);
        else if (c.equals("scalar")) scalar(p[1], p.length > 2 ? Integer.parseInt(p[2]) : 200);
        else if (c.equals("bytes")) bytesSearch(p[1], p.length > 2 ? Integer.parseInt(p[2]) : 50);
        else if (c.equals("dump")) dump(p[1], Integer.parseInt(p[2]));
        else if (c.equals("extrefs")) extrefs(p[1]);
        else if (c.equals("callers")) callers(p[1], Integer.parseInt(p[2]));
        else if (c.equals("near")) near(p[1]);
        else if (c.equals("insn")) insn(l.substring(5).trim());
        else if (c.equals("syms")) syms(l.substring(5).trim());
        else if (c.equals("ptrs")) ptrs(p[1], Integer.parseInt(p[2]));
        else if (c.equals("cstr")) cstr(p[1], p.length > 2 ? Integer.parseInt(p[2]) : 1);
        else if (c.equals("decompall")) decompall(p[1], Integer.parseInt(p[2]));
        else if (c.equals("insnall")) insnall(p[1], l.substring(l.indexOf(p[1]) + p[1].length()).trim());
        else if (c.equals("disasm")) disasm(p[1], Integer.parseInt(p[2]));
        else out.println("unknown command");
    }

    // disasm <addr> <n>: n instructions from addr (disassembles undefined bytes on the fly)
    void disasm(String at, int n) throws Exception {
        Address ad = addr(at);
        Instruction first = currentProgram.getListing().getInstructionAt(ad);
        if (first == null) first = currentProgram.getListing().getInstructionAfter(ad);
        if (first != null) ad = first.getAddress();
        for (int i = 0; i < n; i++) {
            Instruction ins = currentProgram.getListing().getInstructionAt(ad);
            if (ins == null) { disassemble(ad); ins = currentProgram.getListing().getInstructionAt(ad); }
            if (ins == null) { out.println("   " + ad + " ??"); return; }
            out.println("   " + ad + " " + ins + "   " + fname(getFunctionContaining(ad)));
            ad = ins.getMaxAddress().add(1);
        }
    }

    Address addr(String s) {
        if (s.startsWith("0x")) s = s.substring(2);
        return currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(Long.parseUnsignedLong(s, 16));
    }

    Function func(String t) {
        if (t.matches("(0x)?[0-9a-fA-F]{6,}")) {
            Address ad = addr(t);
            Function f = getFunctionContaining(ad);
            if (f != null) return f;
            try { disassemble(ad); f = createFunction(ad, null); } catch (Exception e) { }   // -noanalysis project: make it on demand
            if (f != null) return f;
        }
        for (Function f : currentProgram.getFunctionManager().getFunctions(true))
            if (f.getName().equals(t) || f.getName(true).equals(t)) return f;
        return null;
    }

    String fname(Function f) { return f == null ? "?" : f.getName(true) + "@" + f.getEntryPoint(); }

    void strings(String re) {
        Pattern pat = Pattern.compile(re);
        Listing lst = currentProgram.getListing();
        int n = 0;
        for (Data d : lst.getDefinedData(true)) {
            if (!d.hasStringValue()) continue;
            StringDataInstance s = StringDataInstance.getStringDataInstance(d);
            String v = s.getStringValue();
            if (v == null || !pat.matcher(v).find()) continue;
            if (++n > 400) { out.println("... truncated"); break; }
            out.println(d.getAddress() + " \"" + v.replace("\n", "\\n") + "\"");
            Set<String> fs = new TreeSet<>();
            for (Reference r : getReferencesTo(d.getAddress())) {
                Function f = getFunctionContaining(r.getFromAddress());
                fs.add("   <- " + r.getFromAddress() + " " + fname(f));
            }
            for (String x : fs) out.println(x);
        }
    }

    void funcs(String re) {
        Pattern pat = Pattern.compile(re);
        for (Function f : currentProgram.getFunctionManager().getFunctions(true))
            if (pat.matcher(f.getName(true)).find()) out.println(fname(f) + " size " + f.getBody().getNumAddresses());
    }

    DecompInterface dec() {
        if (dec == null) {
            dec = new DecompInterface();
            DecompileOptions o = new DecompileOptions();
            dec.setOptions(o);
            dec.openProgram(currentProgram);
        }
        return dec;
    }

    String decompile(Function f) {
        DecompileResults r = dec().decompileFunction(f, 180, monitor);
        if (r == null || r.getDecompiledFunction() == null) return "// decompile failed " + fname(f) + "\n";
        return r.getDecompiledFunction().getC();
    }

    void decomp(String t, int depth) throws Exception {
        Function root = func(t);
        if (root == null) { out.println("no function " + t); return; }
        LinkedHashSet<Function> seen = new LinkedHashSet<>();
        List<Function> level = new ArrayList<>(); level.add(root); seen.add(root);
        for (int d = 0; d < depth; d++) {
            List<Function> next = new ArrayList<>();
            for (Function f : level)
                for (Function g : f.getCalledFunctions(monitor)) {
                    if (g.isThunk() || g.isExternal() || seen.contains(g)) continue;
                    if (g.getBody().getNumAddresses() > 20000) continue;
                    seen.add(g); next.add(g);
                }
            level = next;
        }
        String fn = root.getName().replaceAll("[^A-Za-z0-9_]", "_") + "_" + root.getEntryPoint() + (depth > 0 ? "_d" + depth : "") + ".c";
        try (PrintWriter w = new PrintWriter(new FileWriter(new File(decompDir, fn)))) {
            for (Function f : seen) {
                w.println("// ===== " + fname(f));
                w.println(decompile(f));
            }
        }
        out.println("wrote " + fn + " (" + seen.size() + " functions)");
        for (Function f : seen) out.println("   " + fname(f));
    }

    void xrefs(String t) {
        Function f = func(t);
        if (f != null && (t.matches("(0x)?[0-9a-fA-F]{6,}") ? f.getEntryPoint().equals(addr(t)) : true)) {
            out.println("function " + fname(f));
            for (Reference r : getReferencesTo(f.getEntryPoint()))
                out.println("   caller " + r.getFromAddress() + " " + fname(getFunctionContaining(r.getFromAddress())) + " " + r.getReferenceType());
            for (Function g : f.getCalledFunctions(monitor)) out.println("   callee " + fname(g));
            return;
        }
        Address ad = addr(t);
        for (Reference r : getReferencesTo(ad))
            out.println("   ref " + r.getFromAddress() + " " + fname(getFunctionContaining(r.getFromAddress())) + " " + r.getReferenceType());
    }

    // references to an imported (external) function, also through its thunks
    void extrefs(String name) {
        for (Function f : currentProgram.getFunctionManager().getExternalFunctions()) {
            if (!f.getName().equals(name)) continue;
            out.println("external " + f.getName(true));
            for (Address a : f.getFunctionThunkAddresses(true) == null ? new Address[0] : f.getFunctionThunkAddresses(true))
                for (Reference r : getReferencesTo(a))
                    out.println("   thunk-ref " + r.getFromAddress() + " " + fname(getFunctionContaining(r.getFromAddress())));
            for (Reference r : currentProgram.getReferenceManager().getReferencesTo(f.getEntryPoint()))
                for (Reference r2 : getReferencesTo(r.getFromAddress()))
                    out.println("   ref " + r2.getFromAddress() + " " + fname(getFunctionContaining(r2.getFromAddress())));
            for (Reference r : currentProgram.getReferenceManager().getReferencesTo(f.getEntryPoint()))
                out.println("   iat " + r.getFromAddress() + " " + fname(getFunctionContaining(r.getFromAddress())));
        }
    }

    void callers(String t, int depth) {
        Function f = func(t);
        callersRec(f, depth, "", new HashSet<>());
    }

    void callersRec(Function f, int depth, String ind, Set<Function> seen) {
        out.println(ind + fname(f));
        if (depth == 0 || !seen.add(f)) return;
        Set<Function> cs = f.getCallingFunctions(monitor);
        for (Function g : cs) callersRec(g, depth - 1, ind + "  ", seen);
    }

    void rename(String at, String name) throws Exception {
        Address ad = addr(at);
        Function f = getFunctionAt(ad);
        if (f == null) f = createFunction(ad, name);
        if (f == null) { out.println("cannot create function at " + at); return; }
        f.setName(name, SourceType.USER_DEFINED);
        out.println("renamed " + fname(f));
    }

    void label(String at, String name) throws Exception {
        Address ad = addr(at);
        Symbol s = createLabel(ad, name, true, SourceType.USER_DEFINED);
        out.println("label " + s.getName() + " at " + ad);
    }

    void scalar(String hex, int max) {
        long v = Long.parseUnsignedLong(hex.replace("0x", ""), 16);
        int n = 0;
        InstructionIterator it = currentProgram.getListing().getInstructions(true);
        while (it.hasNext()) {
            Instruction ins = it.next();
            for (int i = 0; i < ins.getNumOperands(); i++) {
                for (Object o : ins.getOpObjects(i)) {
                    if (o instanceof Scalar) {
                        Scalar s = (Scalar) o;
                        if (s.getUnsignedValue() == v || s.getValue() == v) {
                            out.println("   " + ins.getAddress() + " " + ins + "  " + fname(getFunctionContaining(ins.getAddress())));
                            if (++n >= max) { out.println("... max"); return; }
                        }
                    }
                }
            }
        }
    }

    void bytesSearch(String hex, int max) {
        byte[] b = new byte[hex.length() / 2];
        for (int i = 0; i < b.length; i++) b[i] = (byte) Integer.parseInt(hex.substring(2 * i, 2 * i + 2), 16);
        Memory m = currentProgram.getMemory();
        Address start = m.getMinAddress();
        int n = 0;
        while (start != null) {
            Address f = m.findBytes(start, b, null, true, monitor);
            if (f == null) break;
            out.println("   hit " + f + " in " + m.getBlock(f).getName());
            for (Reference r : getReferencesTo(f))
                out.println("      ref " + r.getFromAddress() + " " + fname(getFunctionContaining(r.getFromAddress())));
            if (++n >= max) break;
            start = f.add(1);
        }
    }

    // instructions whose text matches regex (e.g. "CALL.*\+ 0x108\]")
    void insn(String re) {
        Pattern pat = Pattern.compile(re);
        int n = 0;
        InstructionIterator it = currentProgram.getListing().getInstructions(true);
        while (it.hasNext()) {
            Instruction ins = it.next();
            String s = ins.toString();
            if (pat.matcher(s).find()) {
                out.println("   " + ins.getAddress() + " " + s + "  " + fname(getFunctionContaining(ins.getAddress())));
                if (++n > 300) { out.println("... truncated"); return; }
            }
        }
    }

    void syms(String re) {
        Pattern pat = Pattern.compile(re);
        int n = 0;
        for (Symbol s : currentProgram.getSymbolTable().getAllSymbols(true)) {
            if (pat.matcher(s.getName(true)).find()) {
                out.println("   " + s.getName(true) + " at " + s.getAddress());
                if (++n > 500) { out.println("... truncated"); return; }
            }
        }
    }

    // nearest symbol at or before addr
    void near(String at) {
        Address ad = addr(at);
        SymbolTable st = currentProgram.getSymbolTable();
        for (int i = 0; i < 0x4000; i += 8) {
            Address b = ad.subtract(i);
            Symbol s = st.getPrimarySymbol(b);
            if (s != null && !s.getName().startsWith("PTR_") && !s.getName().startsWith("DAT_")) { out.println("   " + s.getName(true) + " at " + b + " (+0x" + Integer.toHexString(i) + ")"); return; }
            if (s != null && i > 0) out.println("   (" + s.getName() + " at " + b + ")");
        }
    }

    // n pointers from addr, with function names
    void ptrs(String at, int n) throws Exception {
        Address ad = addr(at);
        for (int i = 0; i < n; i++) {
            long v = currentProgram.getMemory().getLong(ad.add(8L * i));
            Address t = currentProgram.getAddressFactory().getDefaultAddressSpace().getAddress(v);
            Function f = getFunctionAt(t);
            Symbol s = currentProgram.getSymbolTable().getPrimarySymbol(t);
            String nm = f != null ? f.getName(true) : (s != null ? s.getName() : "");
            out.println(String.format("   +0x%03x %s %s", 8 * i, t, nm));
        }
    }

    // null-terminated strings starting at addr (n consecutive)
    void cstr(String at, int n) throws Exception {
        Address ad = addr(at);
        for (int k = 0; k < n; k++) {
            StringBuilder sb = new StringBuilder();
            byte b;
            int i = 0;
            while ((b = currentProgram.getMemory().getByte(ad.add(i))) != 0 && i < 400) { sb.append((char) (b & 0xff)); i++; }
            out.println("   " + ad + " \"" + sb + "\"");
            ad = ad.add(i + 1);
            while (currentProgram.getMemory().getByte(ad) == 0) ad = ad.add(1);
        }
    }

    // decompile every function into <dir>\shard_NN.c (header: // ===== name@addr size N stack S)
    void decompall(String dir, int shards) throws Exception {
        new File(dir).mkdirs();
        PrintWriter[] w = new PrintWriter[shards];
        for (int i = 0; i < shards; i++) w[i] = new PrintWriter(new FileWriter(dir + String.format("\\shard_%02d.c", i)));
        int n = 0, fail = 0;
        for (Function f : currentProgram.getFunctionManager().getFunctions(true)) {
            if (f.isThunk() || f.isExternal()) continue;
            String c;
            try { c = decompile(f); } catch (Exception e) { c = "// decompile failed " + e + "\n"; }
            if (c.startsWith("// decompile failed")) fail++;
            PrintWriter o = w[n % shards];
            o.println("// ===== " + fname(f) + " size " + f.getBody().getNumAddresses() + " stack " + f.getStackFrame().getFrameSize());
            o.println(c);
            if (++n % 2000 == 0) { out.println("   " + n + " functions"); out.flush(); for (PrintWriter x : w) x.flush(); }
        }
        for (PrintWriter x : w) x.close();
        out.println("decompiled " + n + " functions, failed " + fail);
    }

    // every instruction matching regex, no limit, to a file: addr|function|text
    void insnall(String file, String re) throws Exception {
        Pattern pat = Pattern.compile(re);
        int n = 0;
        try (PrintWriter o = new PrintWriter(new FileWriter(file))) {
            InstructionIterator it = currentProgram.getListing().getInstructions(true);
            while (it.hasNext()) {
                Instruction ins = it.next();
                String s = ins.toString();
                if (pat.matcher(s).find()) { o.println(ins.getAddress() + "|" + fname(getFunctionContaining(ins.getAddress())) + "|" + s); n++; }
            }
        }
        out.println("insnall " + n + " hits -> " + file);
    }

    void dump(String at, int len) throws Exception {
        Address ad = addr(at);
        byte[] b = new byte[len];
        currentProgram.getMemory().getBytes(ad, b);
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < len; i++) {
            if (i % 16 == 0) sb.append("\n   " + ad.add(i) + " ");
            sb.append(String.format("%02x ", b[i] & 0xff));
        }
        out.println(sb);
    }
}
