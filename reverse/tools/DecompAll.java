import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import java.io.*;
public class DecompAll extends GhidraScript {
  public void run() throws Exception {
    String out = getScriptArgs().length>0 ? getScriptArgs()[0] : "decomp.c";
    DecompInterface di = new DecompInterface();
    di.openProgram(currentProgram);
    PrintWriter pw = new PrintWriter(new FileWriter(out));
    FunctionIterator it = currentProgram.getFunctionManager().getFunctions(true);
    int n=0;
    while (it.hasNext()) {
      Function f = it.next();
      DecompileResults r = di.decompileFunction(f, 60, monitor);
      pw.println("// ==== " + f.getName() + " @ " + f.getEntryPoint());
      if (r.decompileCompleted()) pw.println(r.getDecompiledFunction().getC());
      else pw.println("// FAILED: " + r.getErrorMessage());
      n++;
    }
    pw.close();
    println("decompiled " + n);
  }
}
