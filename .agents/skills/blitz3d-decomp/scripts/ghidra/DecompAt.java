// Decompile functions at given addresses (and list their callers). Args: OUTFILE addr [addr ...]
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;
import java.io.*;

public class DecompAt extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        DecompInterface dec = new DecompInterface();
        dec.openProgram(currentProgram);
        PrintWriter pw = new PrintWriter(new FileWriter(args[0]));
        for (int i = 1; i < args.length; i++) {
            Function f = getFunctionContaining(toAddr(args[i]));
            if (f == null) { pw.println("// no function at " + args[i]); continue; }
            pw.println("\n// ===== " + f.getName() + " @ " + f.getEntryPoint());
            for (Reference r : getReferencesTo(f.getEntryPoint())) {
                Function c = getFunctionContaining(r.getFromAddress());
                pw.println("//   called from " + r.getFromAddress() + " in " + (c == null ? "?" : c.getName()));
            }
            DecompileResults res = dec.decompileFunction(f, 120, monitor);
            pw.println(res.decompileCompleted() ? res.getDecompiledFunction().getC() : "// failed " + res.getErrorMessage());
        }
        pw.close();
    }
}
