/****************************************************************************
** Meta object code from reading C++ file 'genericobjectinspector.h'
**
** Created by: The Qt Meta Object Compiler version 69 (Qt 6.9.0)
**
** WARNING! All changes made in this file will be lost!
*****************************************************************************/

#include "genericobjectinspector.h"
#include <QtCore/qmetatype.h>

#include <QtCore/qtmochelpers.h>

#include <memory>


#include <QtCore/qxptype_traits.h>
#if !defined(Q_MOC_OUTPUT_REVISION)
#error "The header file 'genericobjectinspector.h' doesn't include <QObject>."
#elif Q_MOC_OUTPUT_REVISION != 69
#error "This file was generated using the moc from 6.9.0. It"
#error "cannot be used with the include files from this version of Qt."
#error "(The moc has changed too much.)"
#endif

#ifndef Q_CONSTINIT
#define Q_CONSTINIT
#endif

QT_WARNING_PUSH
QT_WARNING_DISABLE_DEPRECATED
QT_WARNING_DISABLE_GCC("-Wuseless-cast")
namespace {
struct qt_meta_tag_ZN7omnetpp5qtenv22GenericObjectInspectorE_t {};
} // unnamed namespace

template <> constexpr inline auto omnetpp::qtenv::GenericObjectInspector::qt_create_metaobjectdata<qt_meta_tag_ZN7omnetpp5qtenv22GenericObjectInspectorE_t>()
{
    namespace QMC = QtMocConstants;
    QtMocHelpers::StringRefStorage qt_stringData {
        "omnetpp::qtenv::GenericObjectInspector",
        "onTreeViewActivated",
        "",
        "QModelIndex",
        "index",
        "onDataEdited",
        "gatherVisibleDataIfSafe",
        "createContextMenu",
        "pos",
        "copySelectedLineToClipboard",
        "onlyHighlightedPart",
        "cycleSelectedSubtreeMode",
        "setMode",
        "Mode",
        "mode",
        "toGroupedMode",
        "toFlatMode",
        "toInheritanceMode",
        "toChildrenMode",
        "toPacketMode"
    };

    QtMocHelpers::UintData qt_methods {
        // Slot 'onTreeViewActivated'
        QtMocHelpers::SlotData<void(const QModelIndex &)>(1, 2, QMC::AccessProtected, QMetaType::Void, {{
            { 0x80000000 | 3, 4 },
        }}),
        // Slot 'onDataEdited'
        QtMocHelpers::SlotData<void()>(5, 2, QMC::AccessProtected, QMetaType::Void),
        // Slot 'gatherVisibleDataIfSafe'
        QtMocHelpers::SlotData<void()>(6, 2, QMC::AccessProtected, QMetaType::Void),
        // Slot 'createContextMenu'
        QtMocHelpers::SlotData<void(QPoint)>(7, 2, QMC::AccessProtected, QMetaType::Void, {{
            { QMetaType::QPoint, 8 },
        }}),
        // Slot 'copySelectedLineToClipboard'
        QtMocHelpers::SlotData<void(bool)>(9, 2, QMC::AccessProtected, QMetaType::Void, {{
            { QMetaType::Bool, 10 },
        }}),
        // Slot 'cycleSelectedSubtreeMode'
        QtMocHelpers::SlotData<void()>(11, 2, QMC::AccessProtected, QMetaType::Void),
        // Slot 'setMode'
        QtMocHelpers::SlotData<void(Mode)>(12, 2, QMC::AccessProtected, QMetaType::Void, {{
            { 0x80000000 | 13, 14 },
        }}),
        // Slot 'toGroupedMode'
        QtMocHelpers::SlotData<void()>(15, 2, QMC::AccessProtected, QMetaType::Void),
        // Slot 'toFlatMode'
        QtMocHelpers::SlotData<void()>(16, 2, QMC::AccessProtected, QMetaType::Void),
        // Slot 'toInheritanceMode'
        QtMocHelpers::SlotData<void()>(17, 2, QMC::AccessProtected, QMetaType::Void),
        // Slot 'toChildrenMode'
        QtMocHelpers::SlotData<void()>(18, 2, QMC::AccessProtected, QMetaType::Void),
        // Slot 'toPacketMode'
        QtMocHelpers::SlotData<void()>(19, 2, QMC::AccessProtected, QMetaType::Void),
    };
    QtMocHelpers::UintData qt_properties {
    };
    QtMocHelpers::UintData qt_enums {
    };
    return QtMocHelpers::metaObjectData<GenericObjectInspector, qt_meta_tag_ZN7omnetpp5qtenv22GenericObjectInspectorE_t>(QMC::MetaObjectFlag{}, qt_stringData,
            qt_methods, qt_properties, qt_enums);
}
Q_CONSTINIT const QMetaObject omnetpp::qtenv::GenericObjectInspector::staticMetaObject = { {
    QMetaObject::SuperData::link<Inspector::staticMetaObject>(),
    qt_staticMetaObjectStaticContent<qt_meta_tag_ZN7omnetpp5qtenv22GenericObjectInspectorE_t>.stringdata,
    qt_staticMetaObjectStaticContent<qt_meta_tag_ZN7omnetpp5qtenv22GenericObjectInspectorE_t>.data,
    qt_static_metacall,
    nullptr,
    qt_staticMetaObjectRelocatingContent<qt_meta_tag_ZN7omnetpp5qtenv22GenericObjectInspectorE_t>.metaTypes,
    nullptr
} };

void omnetpp::qtenv::GenericObjectInspector::qt_static_metacall(QObject *_o, QMetaObject::Call _c, int _id, void **_a)
{
    auto *_t = static_cast<GenericObjectInspector *>(_o);
    if (_c == QMetaObject::InvokeMetaMethod) {
        switch (_id) {
        case 0: _t->onTreeViewActivated((*reinterpret_cast< std::add_pointer_t<QModelIndex>>(_a[1]))); break;
        case 1: _t->onDataEdited(); break;
        case 2: _t->gatherVisibleDataIfSafe(); break;
        case 3: _t->createContextMenu((*reinterpret_cast< std::add_pointer_t<QPoint>>(_a[1]))); break;
        case 4: _t->copySelectedLineToClipboard((*reinterpret_cast< std::add_pointer_t<bool>>(_a[1]))); break;
        case 5: _t->cycleSelectedSubtreeMode(); break;
        case 6: _t->setMode((*reinterpret_cast< std::add_pointer_t<Mode>>(_a[1]))); break;
        case 7: _t->toGroupedMode(); break;
        case 8: _t->toFlatMode(); break;
        case 9: _t->toInheritanceMode(); break;
        case 10: _t->toChildrenMode(); break;
        case 11: _t->toPacketMode(); break;
        default: ;
        }
    }
}

const QMetaObject *omnetpp::qtenv::GenericObjectInspector::metaObject() const
{
    return QObject::d_ptr->metaObject ? QObject::d_ptr->dynamicMetaObject() : &staticMetaObject;
}

void *omnetpp::qtenv::GenericObjectInspector::qt_metacast(const char *_clname)
{
    if (!_clname) return nullptr;
    if (!strcmp(_clname, qt_staticMetaObjectStaticContent<qt_meta_tag_ZN7omnetpp5qtenv22GenericObjectInspectorE_t>.strings))
        return static_cast<void*>(this);
    return Inspector::qt_metacast(_clname);
}

int omnetpp::qtenv::GenericObjectInspector::qt_metacall(QMetaObject::Call _c, int _id, void **_a)
{
    _id = Inspector::qt_metacall(_c, _id, _a);
    if (_id < 0)
        return _id;
    if (_c == QMetaObject::InvokeMetaMethod) {
        if (_id < 12)
            qt_static_metacall(this, _c, _id, _a);
        _id -= 12;
    }
    if (_c == QMetaObject::RegisterMethodArgumentMetaType) {
        if (_id < 12)
            *reinterpret_cast<QMetaType *>(_a[0]) = QMetaType();
        _id -= 12;
    }
    return _id;
}
QT_WARNING_POP
