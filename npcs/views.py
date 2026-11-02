from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import NPCAdminForm, NPCPersonaForm
from .models import NPCProfile


@login_required
def edit_npc(request, pk):
    """Edit an NPC's persona/behavior.
    Party leader/deputy/executive -> persona + is_active. Staff -> all fields."""
    npc = get_object_or_404(NPCProfile, pk=pk)
    party = npc.party

    is_admin = request.user.is_staff
    can_manage_party = party is not None and party.can_user_manage(request.user)

    if not (is_admin or can_manage_party):
        messages.error(request, "You don't have permission to edit this NPC.")
        return redirect('parties:detail', pk=party.pk) if party else redirect('forum:index')

    form_class = NPCAdminForm if is_admin else NPCPersonaForm

    if request.method == 'POST':
        form = form_class(request.POST, instance=npc)
        if form.is_valid():
            npc_instance = form.save(commit=False)
            if 'persona' in form.changed_data:
                npc_instance.persona_manually_edited = True
            npc_instance.save()
            messages.success(request, 'NPC updated successfully!')
            return redirect('parties:detail', pk=party.pk) if party else redirect('forum:index')
    else:
        form = form_class(instance=npc)

    context = {
        'form': form,
        'npc': npc,
        'party': party,
        'is_admin': is_admin,
    }
    return render(request, 'edit_npc.html', context)
