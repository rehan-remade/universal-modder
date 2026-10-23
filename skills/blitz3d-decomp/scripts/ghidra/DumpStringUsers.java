// Decompiles every function that references (directly or via one pointer hop) any string containing one
// of the needles given as script args. Output: one .c file per needle in the out dir (first arg).
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;
import java.util.*;

public class DumpStringUsers extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        File outDir = new File(args[0]);
        outDir.mkdirs();
        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);
        Listing listing = currentProgram.getListing();
        ReferenceManager rm = currentProgram.getReferenceManager();
        List<String> needles = new ArrayList<String>();
        for (int a = 1; a < args.length; a++) {
            if (args[a].startsWith("@")) { // needleFile: one needle per line (cmd.exe mangles % in args)
                for (String l : java.nio.file.Files.readAllLines(java.nio.file.Paths.get(args[a].substring(1)))) if (!l.isEmpty()) needles.add(l);
            } else needles.add(args[a]);
        }
        for (String needle : needles) {
            Set<Function> funcs = new LinkedHashSet<Function>();
            StringBuilder log = new StringBuilder();
            DataIterator it = listing.getDefinedData(true);
            while (it.hasNext()) {
                Data d = it.next();
                if (!d.hasStringValue()) continue;
                Object v = d.getValue();
                if (v == null || !v.toString().contains(needle)) continue;
                log.append("// string ").append(d.getAddress()).append(" ").append(v).append("\n");
                List<Address> targets = new ArrayList<Address>();
                targets.add(d.getAddress());
                for (Reference r : rm.getReferencesTo(d.getAddress())) {
                    Function f = getFunctionContaining(r.getFromAddress());
                    if (f != null) funcs.add(f); else targets.add(r.getFromAddress());
                }
                for (int t = 1; t < targets.size(); t++) {
                    for (Reference r : rm.getReferencesTo(targets.get(t))) {
                        Function f = getFunctionContaining(r.getFromAddress());
                        log.append("//   via ptr ").append(targets.get(t)).append(" from ").append(r.getFromAddress()).append("\n");
                        if (f != null) funcs.add(f);
                    }
                }
            }
            String safe = needle.replaceAll("[^A-Za-z0-9_.]", "_");
            PrintWriter pw = new PrintWriter(new FileWriter(new File(outDir, safe + ".c")));
            pw.print(log);
            for (Function f : funcs) {
                DecompileResults res = dec.decompileFunction(f, 120, monitor);
                pw.println("\n// ===== " + f.getName() + " @ " + f.getEntryPoint() + " size " + f.getBody().getNumAddresses());
                pw.println(res.decompileCompleted() ? res.getDecompiledFunction().getC() : "// decompile failed: " + res.getErrorMessage());
            }
            pw.close();
            println(needle + ": " + funcs.size() + " functions");
        }
    }
}
